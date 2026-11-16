import os
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    # Configurações do Banco de Dados (PostgreSQL no Railway ou SQLite local)
    basedir = os.path.abspath(os.path.dirname(__file__))
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        # Garante o uso do driver psycopg (versão 3 compatível com Python 3.13)
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '../database.db')

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Usa a SECRET_KEY do Railway ou gera uma chave segura aleatória
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    db.init_app(app)

    # Configuração do Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Por favor, faça login para acessar o sistema.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import Usuario
        return db.session.get(Usuario, int(user_id))

    # Rota pública para serviços de ping / cron job manterem o servidor acordado
    @app.route('/ping')
    def ping():
        return "OK - Servidor Ativo", 200

    # Rota de Cadastro de Novos Usuários
    @app.route('/cadastro', methods=['GET', 'POST'])
    def cadastro():
        from app.models import Usuario, Configuracao

        if current_user.is_authenticated:
            return redirect(url_for('index'))

        # Permite trancar novos cadastros no Railway criando a variável BLOQUEAR_CADASTRO=true
        if os.environ.get('BLOQUEAR_CADASTRO', '').lower() == 'true':
            flash('Novos cadastros estão temporariamente desativados.', 'warning')
            return redirect(url_for('login'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            confirma_senha = request.form.get('confirma_senha', '')

            if not username or not password:
                flash('Preencha todos os campos.', 'danger')
            elif password != confirma_senha:
                flash('As senhas não coincidem.', 'danger')
            elif Usuario.query.filter_by(username=username).first():
                flash('Este nome de usuário já está em uso. Escolha outro.', 'danger')
            else:
                try:
                    novo_usuario = Usuario(username=username)
                    novo_usuario.set_password(password)
                    db.session.add(novo_usuario)
                    db.session.flush()  # Gera o ID do usuário antes do commit

                    # Cria a configuração inicial padrão para o novo usuário
                    nova_config = Configuracao(
                        meta_gastos=3000.00,
                        salario_base=0.00,
                        dia_salario=5,
                        usuario_id=novo_usuario.id
                    )
                    db.session.add(nova_config)
                    db.session.commit()

                    login_user(novo_usuario)
                    flash('Conta criada com sucesso! Bem-vindo ao AppMeuBolso.', 'success')
                    return redirect(url_for('index'))
                except ValueError as e:
                    db.session.rollback()
                    flash(str(e), 'danger')
                except Exception as e:
                    db.session.rollback()
                    print(f"[ERRO AO CADASTRAR USUÁRIO]: {e}")
                    flash('Erro ao criar conta. Tente novamente.', 'danger')

        return render_template('cadastro.html')

    # Rota de Login
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        from app.models import Usuario

        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            user = Usuario.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('Usuário ou senha incorretos. Tente novamente.', 'danger')

        return render_template('login.html')

    # Rota de Logout
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    # Rota para Alterar Senha
    @app.route('/alterar-senha', methods=['GET', 'POST'])
    @login_required
    def alterar_senha():
        if request.method == 'POST':
            senha_atual = request.form.get('senha_atual')
            nova_senha = request.form.get('nova_senha')
            confirma_senha = request.form.get('confirma_senha')

            if not current_user.check_password(senha_atual):
                flash('A senha atual está incorreta.', 'danger')
            elif nova_senha != confirma_senha:
                flash('A nova senha e a confirmação não coincidem.', 'danger')
            else:
                try:
                    current_user.set_password(nova_senha)
                    db.session.commit()
                    flash('Senha alterada com sucesso!', 'success')
                    return redirect(url_for('index'))
                except ValueError as e:
                    flash(str(e), 'danger')

        return render_template('alterar_senha.html')

    # Rota Principal (Dashboard com Filtro de Mês) - Protegida e Isolada por Usuário
    @app.route('/', methods=['GET', 'POST'])
    @login_required
    def index():
        from app.models import Conta, Transacao, Configuracao, ContaRecorrente

        # Busca ou cria a configuração exclusiva do usuário logado
        config = Configuracao.query.filter_by(usuario_id=current_user.id).first()
        if not config:
            config = Configuracao(
                meta_gastos=3000.00,
                salario_base=0.00,
                dia_salario=5,
                usuario_id=current_user.id
            )
            db.session.add(config)
            db.session.commit()

        # Se o usuário enviou alteração de meta, salário base ou dia do salário pelo dashboard
        if request.method == 'POST':
            try:
                if 'meta_gastos' in request.form:
                    config.meta_gastos = float(request.form.get('meta_gastos', 3000.00))
                if 'salario_base' in request.form:
                    config.salario_base = float(request.form.get('salario_base', 0.00))
                if 'dia_salario' in request.form:
                    config.dia_salario = int(request.form.get('dia_salario', 5))
                db.session.commit()
                return redirect(url_for('index'))
            except Exception as e:
                print(f"[ERRO AO ATUALIZAR CONFIGURAÇÃO]: {e}")
                db.session.rollback()

        # Filtra apenas as contas do usuário logado
        contas = Conta.query.filter_by(usuario_id=current_user.id).all()

        # Define o mês atual (formato YYYY-MM) como padrão ou pega o filtro da URL
        mes_atual = datetime.utcnow().strftime('%Y-%m')
        mes_filtro = request.args.get('mes', mes_atual)

        # Base da query filtrada pelo usuário logado
        query_transacoes = Transacao.query.filter_by(usuario_id=current_user.id)

        # Filtra as transações estritamente pelo mês selecionado
        if mes_filtro:
            try:
                ano, mes = mes_filtro.split('-')
                query_transacoes = query_transacoes.filter(
                    db.extract('year', Transacao.data) == int(ano),
                    db.extract('month', Transacao.data) == int(mes)
                )
            except ValueError:
                pass

        # Pega as últimas transações do mês filtrado para exibir na tabela
        transacoes = query_transacoes.order_by(Transacao.data.desc()).limit(5).all()

        # Calcular totais filtrados pelo mês selecionado
        transacoes_receita = query_transacoes.filter_by(tipo='receita').all()

        # Receitas reais extras das transações
        receitas_transacoes = sum(
            t.valor for t in transacoes_receita
            if t.categoria != 'Investimentos / Poupança'
            and 'Transferência' not in t.descricao
            and 'Guardado' not in t.descricao
        )

        # Total de receitas agora soma o Salário Fixo Mensal configurado + entradas extras
        total_receitas = config.salario_base + receitas_transacoes

        # Dinheiro Guardado (Soma poupanças, transferências e valores guardados)
        total_guardado = sum(
            t.valor for t in transacoes_receita
            if t.categoria == 'Investimentos / Poupança'
            or 'Transferência' in t.descricao
            or 'Guardado' in t.descricao
        )

        total_despesas = sum(t.valor for t in query_transacoes.filter_by(tipo='despesa').all())

        saldo_inicial_total = sum(c.saldo_inicial for c in contas)
        # O saldo total soma receitas e dinheiro guardado, subtraindo despesas
        saldo_total = saldo_inicial_total + total_receitas + total_guardado - total_despesas

        # Buscar Contas Recorrentes apenas do usuário logado
        recorrentes_todas = ContaRecorrente.query.filter_by(usuario_id=current_user.id).all()
        contas_para_vencer = []
        for r in recorrentes_todas:
            if not r.esta_pago_no_mes(mes_filtro):
                contas_para_vencer.append(r)

        # Ordena por dia de vencimento
        contas_para_vencer = sorted(contas_para_vencer, key=lambda x: x.dia_vencimento)

        # Metas e Configurações Dinâmicas
        meta_gastos = config.meta_gastos
        salario_base = config.salario_base
        dia_salario = config.dia_salario
        percentual_gastos = (total_despesas / meta_gastos * 100) if meta_gastos > 0 else 0

        return render_template('dashboard.html',
                               transacoes=transacoes,
                               saldo_total=saldo_total,
                               total_receitas=total_receitas,
                               salario_base=salario_base,
                               dia_salario=dia_salario,
                               total_guardado=total_guardado,
                               total_despesas=total_despesas,
                               meta_gastos=meta_gastos,
                               percentual_gastos=percentual_gastos,
                               mes_atual=mes_filtro,
                               contas_para_vencer=contas_para_vencer)

    # Registro dinâmico seguro de blueprints criados na pasta app/routes/
    routes_dir = os.path.join(basedir, 'routes')
    if os.path.exists(routes_dir):
        for filename in os.listdir(routes_dir):
            if filename.endswith('.py') and filename != '__init__.py':
                mod_name = filename[:-3]
                module = __import__(f'app.routes.{mod_name}', fromlist=['*'])

                # Procura automaticamente qualquer variável que termine com _bp no módulo
                for attr_name in dir(module):
                    if attr_name.endswith('_bp'):
                        blueprint = getattr(module, attr_name)
                        # Garante que não vai registrar o mesmo blueprint duas vezes
                        if blueprint.name not in app.blueprints:
                            app.register_blueprint(blueprint)

    # Criação das tabelas e migrações seguras (sem senhas expostas no código)
    with app.app_context():
        db.create_all()

        from app.models import Usuario
        primeiro_usuario = Usuario.query.first()
        default_user_id = primeiro_usuario.id if primeiro_usuario else 1

        # 1. Migração segura: adiciona usuario_id nas tabelas antigas
        tabelas_para_migrar = ['conta', 'cartao', 'transacao', 'configuracao', 'conta_recorrente']
        for tabela in tabelas_para_migrar:
            try:
                db.session.execute(db.text(f"SELECT usuario_id FROM {tabela} LIMIT 1"))
            except Exception:
                db.session.rollback()
                try:
                    db.session.execute(db.text(f"ALTER TABLE {tabela} ADD COLUMN usuario_id INTEGER DEFAULT {default_user_id}"))
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"[ERRO MIGRACAO {tabela}]: {e}")

        # 2. Migração segura: garante colunas de salário na tabela configuracao
        try:
            db.session.execute(db.text("SELECT salario_base FROM configuracao LIMIT 1"))
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(db.text("ALTER TABLE configuracao ADD COLUMN salario_base FLOAT DEFAULT 0.0"))
                db.session.execute(db.text("ALTER TABLE configuracao ADD COLUMN dia_salario INTEGER DEFAULT 5"))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[ERRO AO ADICIONAR COLUNAS DE SALARIO]: {e}")

        # 3. Migração segura: garante colunas essenciais na tabela transacao (como categoria)
        colunas_transacao = [
            ('categoria', "TEXT DEFAULT 'Geral'"),
            ('cartao_id', 'INTEGER'),
            ('parcela_atual', 'INTEGER DEFAULT 1'),
            ('total_parcelas', 'INTEGER DEFAULT 1')
        ]
        for col_nome, col_tipo in colunas_transacao:
            try:
                db.session.execute(db.text(f"SELECT {col_nome} FROM transacao LIMIT 1"))
            except Exception:
                db.session.rollback()
                try:
                    db.session.execute(db.text(f"ALTER TABLE transacao ADD COLUMN {col_nome} {col_tipo}"))
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"[ERRO AO ADICIONAR COLUNA {col_nome}]: {e}")

    return app