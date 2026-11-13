from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        # Validação rigorosa de senha forte
        if len(password) < 6:
            raise ValueError("A senha deve ter pelo menos 6 caracteres.")
        if not any(char.isdigit() for char in password) or not any(char.isalpha() for char in password):
            raise ValueError("A senha deve conter uma combinação de letras e números para ser segura.")

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Conta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    saldo_inicial = db.Column(db.Float, default=0.0)

    @property
    def saldo_atual(self):
        # Soma todas as receitas vinculadas a esta conta
        total_receitas = sum(t.valor for t in self.transacoes if t.tipo == 'receita')
        # Soma todas as despesas vinculadas a esta conta
        total_despesas = sum(t.valor for t in self.transacoes if t.tipo == 'despesa')
        # Retorna o saldo inicial + receitas - despesas
        return self.saldo_inicial + total_receitas - total_despesas


class Cartao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    limite = db.Column(db.Float, nullable=False, default=0.0)
    dia_fechamento = db.Column(db.Integer, nullable=False, default=1)
    dia_vencimento = db.Column(db.Integer, nullable=False, default=10)

    @property
    def fatura_atual(self):
        # Soma todas as despesas vinculadas a este cartão
        return sum(t.valor for t in self.transacoes if t.tipo == 'despesa')

    @property
    def limite_disponivel(self):
        # Calcula quanto limite ainda resta
        return self.limite - self.fatura_atual


class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(150), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'receita' ou 'despesa'

    # Campo de Categoria adicionado para suportar a seleção estruturada do cliente
    categoria = db.Column(db.String(100), nullable=False, default='Diversos')

    data = db.Column(db.DateTime, default=datetime.utcnow)

    # Vínculo com Conta (opcional caso o lançamento seja feito no cartão)
    conta_id = db.Column(db.Integer, db.ForeignKey('conta.id'), nullable=True)
    conta = db.relationship('Conta', backref=db.backref('transacoes', lazy=True, cascade='all, delete-orphan'))

    # Vínculo com Cartão de Crédito (opcional)
    cartao_id = db.Column(db.Integer, db.ForeignKey('cartao.id'), nullable=True)
    cartao = db.relationship('Cartao', backref=db.backref('transacoes', lazy=True, cascade='all, delete-orphan'))

    # Controle de Parcelamento
    parcela_atual = db.Column(db.Integer, default=1)
    total_parcelas = db.Column(db.Integer, default=1)


class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meta_gastos = db.Column(db.Float, default=3000.00, nullable=False)


class ContaRecorrente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(150), nullable=False)  # Ex: Aluguel, Internet, Financiamento
    valor = db.Column(db.Float, nullable=False)
    dia_vencimento = db.Column(db.Integer, nullable=False)  # Dia do mês (ex: 5, 10, 20)
    categoria = db.Column(db.String(100), nullable=False, default='Contas Fixas')

    # Classificação de Despesa (Fixa, Variável, Parcelamento/Dívida)
    tipo_despesa = db.Column(db.String(50), nullable=False, default='Fixa')

    # Controle de Parcelamentos
    parcela_atual = db.Column(db.Integer, default=1)
    total_parcelas = db.Column(db.Integer, default=1)
    mes_inicio = db.Column(db.String(7), nullable=True)  # Formato 'YYYY-MM'

    # Guarda o mês (formato 'YYYY-MM') em que foi pago pela última vez
    ultimo_mes_pago = db.Column(db.String(7), nullable=True)

    # Conta padrão de onde o dinheiro sai quando você clica em "Pagar"
    conta_id = db.Column(db.Integer, db.ForeignKey('conta.id'), nullable=True)
    conta = db.relationship('Conta', backref=db.backref('recorrentes', lazy=True))

    def esta_pago_no_mes(self, mes_referencia):
        return self.ultimo_mes_pago == mes_referencia

    @property
    def mes_termino(self):
        """Calcula o mês em que o parcelamento vai acabar"""
        if self.total_parcelas <= 1 or not self.mes_inicio:
            return None
        try:
            ano, mes = map(int, self.mes_inicio.split('-'))
            mes_total = mes + (self.total_parcelas - 1)
            ano += (mes_total - 1) // 12
            mes = ((mes_total - 1) % 12) + 1
            return f"{ano:04d}-{mes:02d}"
        except Exception:
            return None