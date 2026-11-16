from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Transacao, Conta, Cartao

transacoes_bp = Blueprint('transacoes', __name__, url_prefix='/transacoes')


@transacoes_bp.route('/')
@login_required
def index():
    tipo_filtro = request.args.get('tipo')
    conta_filtro = request.args.get('conta_id', type=int)

    # Define o mês atual (formato YYYY-MM) como padrão
    mes_atual = datetime.utcnow().strftime('%Y-%m')
    mes_filtro = request.args.get('mes', mes_atual)

    # Base da query restrita ao usuário logado
    query = Transacao.query.filter_by(usuario_id=current_user.id)

    if tipo_filtro:
        query = query.filter_by(tipo=tipo_filtro)
    if conta_filtro:
        query = query.filter_by(conta_id=conta_filtro)

    # Filtra as transações estritamente pelo mês selecionado
    if mes_filtro:
        try:
            ano, mes = mes_filtro.split('-')
            query = query.filter(
                db.extract('year', Transacao.data) == int(ano),
                db.extract('month', Transacao.data) == int(mes)
            )
        except ValueError:
            pass

    transacoes = query.order_by(Transacao.data.desc()).all()
    contas = Conta.query.filter_by(usuario_id=current_user.id).all()

    return render_template('transacoes/index.html',
                           items=transacoes,
                           contas=contas,
                           tipo_atual=tipo_filtro,
                           conta_atual=conta_filtro,
                           mes_atual=mes_filtro)


@transacoes_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    contas = Conta.query.filter_by(usuario_id=current_user.id).all()
    cartoes = Cartao.query.filter_by(usuario_id=current_user.id).all()

    if request.method == 'POST':
        try:
            descricao = request.form.get('descricao')
            valor = float(request.form.get('valor', 0.0))
            tipo = request.form.get('tipo')
            categoria = request.form.get('categoria')
            forma_pagamento = request.form.get('forma_pagamento')

            # Captura a data informada ou usa a data atual caso venha vazia
            data_str = request.form.get('data')
            data_base = datetime.strptime(data_str, '%Y-%m-%d') if data_str else datetime.utcnow()

            conta_id = None
            cartao_id = None

            # Garante que a conta ou cartão selecionado pertence ao usuário logado
            if forma_pagamento == 'conta':
                cid = request.form.get('conta_id', type=int)
                conta_valida = Conta.query.filter_by(id=cid, usuario_id=current_user.id).first()
                conta_id = conta_valida.id if conta_valida else None
            elif forma_pagamento == 'cartao':
                crid = request.form.get('cartao_id', type=int)
                cartao_valido = Cartao.query.filter_by(id=crid, usuario_id=current_user.id).first()
                cartao_id = cartao_valido.id if cartao_valido else None

            total_parcelas = int(request.form.get('total_parcelas', 1)) if forma_pagamento == 'cartao' else 1

            if forma_pagamento == 'cartao' and total_parcelas > 1 and cartao_id:
                valor_parcela = valor / total_parcelas
                for i in range(1, total_parcelas + 1):
                    dias_a_somar = (i - 1) * 30
                    data_parcela = data_base + timedelta(days=dias_a_somar)

                    nova_transacao = Transacao(
                        descricao=descricao,
                        valor=valor_parcela,
                        tipo=tipo,
                        categoria=categoria,
                        cartao_id=cartao_id,
                        data=data_parcela,
                        parcela_atual=i,
                        total_parcelas=total_parcelas,
                        usuario_id=current_user.id
                    )
                    db.session.add(nova_transacao)
            else:
                nova_transacao = Transacao(
                    descricao=descricao,
                    valor=valor,
                    tipo=tipo,
                    categoria=categoria,
                    conta_id=conta_id,
                    cartao_id=cartao_id,
                    data=data_base,
                    total_parcelas=total_parcelas,
                    usuario_id=current_user.id
                )
                db.session.add(nova_transacao)

            db.session.commit()
            return redirect(url_for('transacoes.index'))
        except Exception as e:
            print(f"[ERRO AO SALVAR TRANSAÇÃO]: {e}")
            db.session.rollback()

    return render_template('transacoes/form.html', contas=contas, cartoes=cartoes)


@transacoes_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    transacao = Transacao.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    contas = Conta.query.filter_by(usuario_id=current_user.id).all()
    cartoes = Cartao.query.filter_by(usuario_id=current_user.id).all()

    if request.method == 'POST':
        try:
            transacao.descricao = request.form.get('descricao')
            transacao.valor = float(request.form.get('valor', 0.0))
            transacao.tipo = request.form.get('tipo')
            transacao.categoria = request.form.get('categoria')

            data_str = request.form.get('data')
            if data_str:
                transacao.data = datetime.strptime(data_str, '%Y-%m-%d')

            forma_pagamento = request.form.get('forma_pagamento')
            transacao.conta_id = None
            transacao.cartao_id = None

            if forma_pagamento == 'conta':
                cid = request.form.get('conta_id', type=int)
                conta_valida = Conta.query.filter_by(id=cid, usuario_id=current_user.id).first()
                transacao.conta_id = conta_valida.id if conta_valida else None
            elif forma_pagamento == 'cartao':
                crid = request.form.get('cartao_id', type=int)
                cartao_valido = Cartao.query.filter_by(id=crid, usuario_id=current_user.id).first()
                transacao.cartao_id = cartao_valido.id if cartao_valido else None

            db.session.commit()
            return redirect(url_for('transacoes.index'))
        except Exception as e:
            print(f"[ERRO AO EDITAR TRANSAÇÃO]: {e}")
            db.session.rollback()

    return render_template('transacoes/form.html', transacao=transacao, contas=contas, cartoes=cartoes)


@transacoes_bp.route('/deletar/<int:id>')
@login_required
def deletar(id):
    transacao = Transacao.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    try:
        db.session.delete(transacao)
        db.session.commit()
    except Exception as e:
        print(f"[ERRO AO EXCLUIR TRANSAÇÃO]: {e}")
        db.session.rollback()

    return redirect(url_for('transacoes.index'))


@transacoes_bp.route('/transferir', methods=['GET', 'POST'])
@login_required
def transferir():
    contas = Conta.query.filter_by(usuario_id=current_user.id).all()

    if request.method == 'POST':
        try:
            descricao = request.form.get('descricao', 'Transferência entre contas')
            valor = float(request.form.get('valor', 0.0))
            conta_origem_id = int(request.form.get('conta_origem_id'))
            conta_destino_id = int(request.form.get('conta_destino_id'))

            # Verifica se ambas as contas pertencem ao usuário logado
            origem = Conta.query.filter_by(id=conta_origem_id, usuario_id=current_user.id).first()
            destino = Conta.query.filter_by(id=conta_destino_id, usuario_id=current_user.id).first()

            if not origem or not destino:
                return render_template('transacoes/transferir.html', contas=contas,
                                       erro="Conta de origem ou destino inválida.")

            if origem.id == destino.id:
                return render_template('transacoes/transferir.html', contas=contas,
                                       erro="A conta de origem e destino devem ser diferentes.")

            saida = Transacao(
                descricao=f"Transferência (Saída): {descricao}",
                valor=valor,
                tipo='despesa',
                categoria='Diversos',
                conta_id=origem.id,
                usuario_id=current_user.id
            )

            entrada = Transacao(
                descricao=f"Transferência (Entrada): {descricao}",
                valor=valor,
                tipo='receita',
                categoria='Receitas / Entradas',
                conta_id=destino.id,
                usuario_id=current_user.id
            )

            db.session.add(saida)
            db.session.add(entrada)
            db.session.commit()

            return redirect(url_for('transacoes.index'))
        except Exception as e:
            print(f"[ERRO NA TRANSFERÊNCIA]: {e}")
            db.session.rollback()

    return render_template('transacoes/transferir.html', contas=contas)