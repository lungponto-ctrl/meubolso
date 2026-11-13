from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models import ContaRecorrente, Conta, Transacao

recorrentes_bp = Blueprint('recorrentes', __name__, url_prefix='/recorrentes')


@recorrentes_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    mes_atual = datetime.utcnow().strftime('%Y-%m')
    mes_filtro = request.args.get('mes', mes_atual)

    if request.method == 'POST':
        descricao = request.form.get('descricao')
        valor = float(request.form.get('valor', 0.0))
        dia_vencimento = int(request.form.get('dia_vencimento', 10))
        categoria = request.form.get('categoria', 'Contas Fixas')
        tipo_despesa = request.form.get('tipo_despesa', 'Fixa')
        total_parcelas = int(request.form.get('total_parcelas', 1))
        conta_id = request.form.get('conta_id')
        conta_id = int(conta_id) if conta_id else None

        if descricao and valor > 0:
            nova_conta = ContaRecorrente(
                descricao=descricao,
                valor=valor,
                dia_vencimento=dia_vencimento,
                categoria=categoria,
                tipo_despesa=tipo_despesa,
                total_parcelas=total_parcelas,
                parcela_atual=1,
                mes_inicio=mes_filtro,
                conta_id=conta_id
            )
            db.session.add(nova_conta)
            db.session.commit()
            flash('Compromisso cadastrado com sucesso!', 'success')
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

    conta_rec.ultimo_mes_pago = mes_filtro

    desc_transacao = f"[Fixa] {conta_rec.descricao}"
    if conta_rec.total_parcelas > 1:
        desc_transacao = f"[Parcela {conta_rec.parcela_atual}/{conta_rec.total_parcelas}] {conta_rec.descricao}"

    nova_transacao = Transacao(
        descricao=desc_transacao,
        valor=conta_rec.valor,
        tipo='despesa',
        categoria=conta_rec.categoria,
        conta_id=conta_rec.conta_id,
        data=datetime.utcnow()
    )

    # Avança a parcela atual ao pagar
    if conta_rec.total_parcelas > 1 and conta_rec.parcela_atual < conta_rec.total_parcelas:
        conta_rec.parcela_atual += 1

    db.session.add(nova_transacao)
    db.session.commit()

    flash(f'Compromisso "{conta_rec.descricao}" marcado como pago!', 'success')
    return redirect(url_for('recorrentes.index', mes=mes_filtro))


@recorrentes_bp.route('/excluir/<int:id>', methods=['POST'])
@login_required
def excluir(id):
    conta_rec = ContaRecorrente.query.get_or_404(id)
    db.session.delete(conta_rec)
    db.session.commit()
    flash('Item removido com sucesso.', 'info')
    return redirect(url_for('recorrentes.index'))