import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    # Configurações do Banco de Dados SQLite
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '../database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'appmeubolso-secret-key'

    db.init_app(app)

    # Rota Principal (Dashboard)
    @app.route('/', methods=['GET', 'POST'])
    def index():
        from app.models import Conta, Transacao, Configuracao

        # Busca ou cria a configuração padrão de meta no banco
        config = Configuracao.query.first()
        if not config:
            config = Configuracao(meta_gastos=3000.00)
            db.session.add(config)
            db.session.commit()

        # Se o usuário enviou uma alteração de meta pelo formulário do dashboard
        if request.method == 'POST':
            try:
                novo_limite = float(request.form.get('meta_gastos', 3000.00))
                config.meta_gastos = novo_limite
                db.session.commit()
                return redirect(url_for('index'))
            except Exception as e:
                print(f"[ERRO AO ATUALIZAR META]: {e}")
                db.session.rollback()

        contas = Conta.query.all()
        transacoes = Transacao.query.order_by(Transacao.data.desc()).limit(5).all()

        # Calcular totais
        total_receitas = sum(t.valor for t in Transacao.query.filter_by(tipo='receita').all())
        total_despesas = sum(t.valor for t in Transacao.query.filter_by(tipo='despesa').all())
        saldo_inicial_total = sum(c.saldo_inicial for c in contas)
        saldo_total = saldo_inicial_total + total_receitas - total_despesas

        # Meta de Gastos Mensal Dinâmica
        meta_gastos = config.meta_gastos
        percentual_gastos = (total_despesas / meta_gastos * 100) if meta_gastos > 0 else 0

        return render_template('dashboard.html',
                               transacoes=transacoes,
                               saldo_total=saldo_total,
                               total_receitas=total_receitas,
                               total_despesas=total_despesas,
                               meta_gastos=meta_gastos,
                               percentual_gastos=percentual_gastos)

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

    # Criação das tabelas do banco de dados se não existirem
    with app.app_context():
        db.create_all()

    return app