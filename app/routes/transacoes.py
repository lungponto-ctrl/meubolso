from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from app.models import Transacao, Conta, Cartao

transacoes_bp = Blueprint('transacoes', __name__, url_prefix='/transacoes')


@transacoes_bp.route('/')
def index():
    tipo_filtro = request.args.get('tipo')
    conta_filtro = request.args.get('conta_id', type=int)

    # Define o mês atual (formato YYYY-MM) como padrão
    mes_atual = datetime.utcnow().strftime('%Y-%m')
    mes_filtro = request.args.get('mes', mes_atual)

    query = Transacao.query

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
    contas = Conta.query.all()

    return render_template('transacoes/index.html',
                           items=transacoes,
                           contas=contas,
                           tipo_atual=tipo_filtro,
                           conta_atual=conta_filtro,
                           mes_atual=mes_filtro)


@transacoes_bp.route('/novo', methods=['GET', 'POST'])
def novo():
    contas = Conta.query.all()
    cartoes = Cartao.query.all()

    if request.method == 'POST':
        try:
            descricao = request.form.get('descricao')
            valor = float(request.form.get('valor', 0.0))
            tipo = request.form.get('tipo')
            forma_pagamento = request.form.get('forma_pagamento')  # 'conta' ou 'cartao'

            # Captura a data informada ou usa a data atual caso venha vazia
            data_str = request.form.get('data')
            data_base = datetime.strptime(data_str, '%Y-%m-%d') if data_str else datetime.utcnow()

            conta_id = request.form.get('conta_id', type=int) if forma_pagamento == 'conta' else None
            cartao_id = request.form.get('cartao_id', type=int) if forma_pagamento == 'cartao' else None
            total_parcelas = int(request.form.get('total_parcelas', 1)) if forma_pagamento == 'cartao' else 1

            if forma_pagamento == 'cartao' and total_parcelas > 1:
                # Divide o valor total entre as parcelas
                valor_parcela = valor / total_parcelas
                for i in range(1, total_parcelas + 1):
                    # Avança 30 dias para cada parcela subsequente
                    dias_a_somar = (i - 1) * 30
                    data_parcela = data_base + timedelta(days=dias_a_somar)

                    # Mantém o nome limpo na descrição e controla as colunas de parcelas
                    nova_transacao = Transacao(
                        descricao=descricao,
                        valor=valor_parcela,
                        tipo=tipo,
                        cartao_id=cartao_id,
                        data=data_parcela,
                        parcela_atual=i,
                        total_parcelas=total_parcelas
                    )
                    db.session.add(nova_transacao)
            else:
                nova_transacao = Transacao(
                    descricao=descricao,
                    valor=valor,
                    tipo=tipo,
                    conta_id=conta_id,
                    cartao_id=cartao_id,
                    data=data_base,
                    total_parcelas=total_parcelas
                )
                db.session.add(nova_transacao)

            db.session.commit()
            return redirect(url_for('transacoes.index'))
        except Exception as e:
            print(f"[ERRO AO SALVAR TRANSAÇÃO]: {e}")
            db.session.rollback()

    return render_template('transacoes/form.html', contas=contas, cartoes=cartoes)


@transacoes_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    transacao = Transacao.query.get_or_404(id)
    contas = Conta.query.all()
    cartoes = Cartao.query.all()

    if request.method == 'POST':
        try:
            transacao.descricao = request.form.get('descricao')
            transacao.valor = float(request.form.get('valor', 0.0))
            transacao.tipo = request.form.get('tipo')

            data_str = request.form.get('data')
            if data_str:
                transacao.data = datetime.strptime(data_str, '%Y-%m-%d')

            forma_pagamento = request.form.get('forma_pagamento')
            transacao.conta_id = request.form.get('conta_id', type=int) if forma_pagamento == 'conta' else None
            transacao.cartao_id = request.form.get('cartao_id', type=int) if forma_pagamento == 'cartao' else None

            db.session.commit()
            return redirect(url_for('transacoes.index'))
        except Exception as e:
            print(f"[ERRO AO EDITAR TRANSAÇÃO]: {e}")
            db.session.rollback()

    return render_template('transacoes/form.html', transacao=transacao, contas=contas, cartoes=cartoes)


@transacoes_bp.route('/deletar/<int:id>')
def deletar(id):
    transacao = Transacao.query.get_or_404(id)
    try:
        db.session.delete(transacao)
        db.session.commit()
    except Exception as e:
        print(f"[ERRO AO EXCLUIR TRANSAÇÃO]: {e}")
        db.session.rollback()

    return redirect(url_for('transacoes.index'))


@transacoes_bp.route('/transferir', methods=['GET', 'POST'])
def transferir():
    contas = Conta.query.all()

    if request.method == 'POST':
        try:
            descricao = request.form.get('descricao', 'Transferência entre contas')
            valor = float(request.form.get('valor', 0.0))
            conta_origem_id = int(request.form.get('conta_origem_id'))
            conta_destino_id = int(request.form.get('conta_destino_id'))

            if conta_origem_id == conta_destino_id:
                return render_template('transacoes/transferir.html', contas=contas,
                                       erro="A conta de origem e destino devem ser diferentes.")

            saida = Transacao(
                descricao=f"Transferência (Saída): {descricao}",
                valor=valor,
                tipo='despesa',
                conta_id=conta_origem_id
            )

            entrada = Transacao(
                descricao=f"Transferência (Entrada): {descricao}",
                valor=valor,
                tipo='receita',
                conta_id=conta_destino_id
            )

            db.session.add(saida)
            db.session.add(entrada)
            db.session.commit()

            return redirect(url_for('transacoes.index'))
        except Exception as e:
            print(f"[ERRO NA TRANSFERÊNCIA]: {e}")
            db.session.rollback()

    return render_template('transacoes/transferir.html', contas=contas)