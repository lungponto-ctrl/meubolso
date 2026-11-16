from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Cartao, Transacao

cartoes_bp = Blueprint('cartoes', __name__, url_prefix='/cartoes')


@cartoes_bp.route('/')
@login_required
def index():
    cartoes = Cartao.query.filter_by(usuario_id=current_user.id).all()
    return render_template('cartoes/index.html', cartoes=cartoes)


@cartoes_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            limite = float(request.form.get('limite', 0.0))
            dia_fechamento = int(request.form.get('dia_fechamento', 1))
            dia_vencimento = int(request.form.get('dia_vencimento', 10))

            novo_cartao = Cartao(
                nome=nome,
                limite=limite,
                dia_fechamento=dia_fechamento,
                dia_vencimento=dia_vencimento,
                usuario_id=current_user.id
            )
            db.session.add(novo_cartao)
            db.session.commit()

            return redirect(url_for('cartoes.index'))
        except Exception as e:
            print(f"[ERRO AO SALVAR CARTÃO]: {e}")
            db.session.rollback()

    return render_template('cartoes/form.html')


@cartoes_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    cartao = Cartao.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()

    if request.method == 'POST':
        try:
            cartao.nome = request.form.get('nome')
            cartao.limite = float(request.form.get('limite', 0.0))
            cartao.dia_fechamento = int(request.form.get('dia_fechamento', 1))
            cartao.dia_vencimento = int(request.form.get('dia_vencimento', 10))

            db.session.commit()
            return redirect(url_for('cartoes.index'))
        except Exception as e:
            print(f"[ERRO AO EDITAR CARTÃO]: {e}")
            db.session.rollback()

    return render_template('cartoes/form.html', cartao=cartao)


@cartoes_bp.route('/deletar/<int:id>')
@login_required
def deletar(id):
    cartao = Cartao.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    try:
        db.session.delete(cartao)
        db.session.commit()
    except Exception as e:
        print(f"[ERRO AO EXCLUIR CARTÃO]: {e}")
        db.session.rollback()

    return redirect(url_for('cartoes.index'))


@cartoes_bp.route('/<int:id>/fatura')
@login_required
def fatura(id):
    cartao = Cartao.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    transacoes = Transacao.query.filter_by(
        cartao_id=cartao.id,
        usuario_id=current_user.id
    ).order_by(Transacao.data.desc()).all()
    return render_template('cartoes/fatura.html', cartao=cartao, transacoes=transacoes)