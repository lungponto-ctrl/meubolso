import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    # Configurações do Banco de Dados SQLite
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '../database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'appmeubolso-secret-key'

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

    # Rota pública para serviços de ping / cron job manterem o Render acordado
    @app.route('/ping')
    def ping():
        return "OK - Servidor Ativo", 200

    # Rota de Login
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        from app.models import Usuario

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

    # Rota Principal (Dashboard com Filtro de Mês) - Protegida
    @app.route('/', methods=['GET', 'POST'])
    @login_required
    def index():
        from app.models import Conta, Transacao, Configuracao, ContaRecorrente

        # Busca ou cria a configuração padrão no banco
        config = Configuracao.query.first()
        if not config:
            config = Configuracao(meta_gastos=3000.00, salario_base=0.00, dia_salario=5)
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

        contas = Conta.query.all()

        # Define o mês atual (formato YYYY-MM) como padrão ou pega o filtro da URL
        mes_atual = datetime.utcnow().strftime('%Y-%m')
        mes_filtro = request.args.get('mes', mes_atual)

        query_transacoes = Transacao.query

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

        # Buscar Contas Recorrentes para verificar vencimentos e alertas do mês
        recorrentes_todas = ContaRecorrente.query.all()
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

    # Criação das tabelas, migrações seguras e configuração da usuária Daniely
    with app.app_context():
        db.create_all()

        # Garante de forma segura que a coluna categoria existe na tabela transacao
        try:
            db.session.execute(db.text("SELECT categoria FROM transacao LIMIT 1"))
        except Exception:
            db.session.execute(db.text("ALTER TABLE transacao ADD COLUMN categoria VARCHAR(100) DEFAULT 'Diversos'"))
            db.session.commit()

        # Garante de forma segura que a coluna salario_base existe na tabela configuracao
        try:
            db.session.execute(db.text("SELECT salario_base FROM configuracao LIMIT 1"))
        except Exception:
            db.session.execute(db.text("ALTER TABLE configuracao ADD COLUMN salario_base FLOAT DEFAULT 0.00"))
            db.session.commit()

        # Garante de forma segura que a coluna dia_salario existe na tabela configuracao
        try:
            db.session.execute(db.text("SELECT dia_salario FROM configuracao LIMIT 1"))
        except Exception:
            db.session.execute(db.text("ALTER TABLE configuracao ADD COLUMN dia_salario INTEGER DEFAULT 5"))
            db.session.commit()

        # Garante que a usuária Daniely está configurada no sistema com a senha correta
        from app.models import Usuario
        user_daniely = Usuario.query.filter_by(username='Daniely').first()
        if not user_daniely:
            user_antigo = Usuario.query.first()
            if user_antigo:
                user_antigo.username = 'Daniely'
                user_antigo.set_password('Dany97883437')
            else:
                novo_usuario = Usuario(username='Daniely')
                novo_usuario.set_password('Dany97883437')
                db.session.add(novo_usuario)
            db.session.commit()

    return app