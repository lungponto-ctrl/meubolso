from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from app.models import Conta

contas_bp = Blueprint('contas', __name__, url_prefix='/contas')


@contas_bp.route('/')
def index():
    contas = Conta.query.all()
    return render_template('contas/index.html', items=contas)


@contas_bp.route('/novo', methods=['GET', 'POST'])
def novo():
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            tipo = request.form.get('tipo', 'corrente')
            saldo_inicial = float(request.form.get('saldo_inicial', 0.0))

            print(f"[DEBUG] Salvando conta: {nome}, {tipo}, {saldo_inicial}")

            nova_conta = Conta(nome=nome, tipo=tipo, saldo_inicial=saldo_inicial)
            db.session.add(nova_conta)
            db.session.commit()

            print("[DEBUG] Conta salva com sucesso!")
            return redirect(url_for('contas.index'))
        except Exception as e:
            print(f"[ERRO AO SALVAR CONTA]: {e}")
            db.session.rollback()

    return render_template('contas/form.html')


@contas_bp.route('/deletar/<int:id>', methods=['POST', 'GET'])
def deletar(id):
    try:
        conta = Conta.query.get_or_404(id)
        db.session.delete(conta)
        db.session.commit()
        print(f"[DEBUG] Conta ID {id} excluída com sucesso!")
    except Exception as e:
        print(f"[ERRO AO EXCLUIR CONTA]: {e}")
        db.session.rollback()

    return redirect(url_for('contas.index'))