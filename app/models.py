from datetime import datetime
from app import db


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