from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models import ContaRecorrente, Conta, Transacao

recorrentes_bp = Blueprint('recorrentes', __name__, url_prefix='/recorrentes')


@recorrentes_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    # Define o mês atual (formato YYYY-MM) ou pega da URL
    mes_atual = datetime.utcnow().strftime('%Y-%m')
    mes_filtro = request.args.get('mes', mes_atual)

    if request.method == 'POST':
        # Cadastro de nova conta recorrente / fatura
        descricao = request.form.get('descricao')
        valor = float(request.form.get('valor', 0.0))
        dia_vencimento = int(request.form.get('dia_vencimento', 10))
        categoria = request.form.get('categoria', 'Contas Fixas')
        conta_id = request.form.get('conta_id')
        conta_id = int(conta_id) if conta_id else None

        if descricao and valor > 0:
            nova_conta = ContaRecorrente(
                descricao=descricao,
                valor=valor,
                dia_vencimento=dia_vencimento,
                categoria=categoria,
                conta_id=conta_id
            )
            db.session.add(nova_conta)
            db.session.commit()
            flash('Conta recorrente cadastrada com sucesso!', 'success')
        else:
            flash('Preencha a descrição e um valor válido.', 'danger')

        return redirect(url_for('recorrentes.index', mes=mes_filtro))

    contas_recorrentes = ContaRecorrente.query.all()
    contas_bancarias = Conta.query.all()

    return render_template('recorrentes.html',
                           contas_recorrentes=contas_recorrentes,
                           contas_bancarias=contas_bancarias,
                           mes_atual=mes_filtro)


@recorrentes_bp.route('/pagar/<int:id>', methods=['POST'])
@login_required
def pagar(id):
    conta_rec = ContaRecorrente.query.get_or_404(id)
    mes_filtro = request.form.get('mes_referencia', datetime.utcnow().strftime('%Y-%m'))

    # Marca como pago no mês atual
    conta_rec.ultimo_mes_pago = mes_filtro

    # Cria automaticamente a transação de despesa vinculada para refletir no saldo
    nova_transacao = Transacao(
        descricao=f"[Recorrente] {conta_rec.descricao}",
        valor=conta_rec.valor,
        tipo='despesa',
        categoria=conta_rec.categoria,
        conta_id=conta_rec.conta_id,
        data=datetime.utcnow()
    )

    db.session.add(nova_transacao)
    db.session.commit()

    flash(f'Conta "{conta_rec.descricao}" marcada como paga e registrada nas despesas!', 'success')
    return redirect(url_for('recorrentes.index', mes=mes_filtro))


@recorrentes_bp.route('/excluir/<int:id>', methods=['POST'])
@login_required
def excluir(id):
    conta_rec = ContaRecorrente.query.get_or_404(id)
    db.session.delete(conta_rec)
    db.session.commit()
    flash('Conta recorrente removida com sucesso.', 'info')
    return redirect(url_for('recorrentes.index'))