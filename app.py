from flask import Flask, request, jsonify
from flask_cors import CORS
import mercadopago
import os
import random
import string
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

sdk = mercadopago.SDK(token)
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) 

# Função utilitária para gerar a chave VIP manual curta
def gerar_chave_vip():
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"VTN-{chars}"

# 1. ROTA PARA LER O PROGRESSO DA META
@app.route('/progresso-atual', methods=['GET'])
def progresso():
    try:
        response = supabase.table('campanha_stats').select('total_arrecadado').eq('id', 1).single().execute()
        return jsonify({"total": float(response.data['total_arrecadado'])})
    except:
        return jsonify({"total": 0.00})

# 2. ROTA DE GERAR PIX (ATUALIZADA E DINÂMICA)
@app.route('/gerar-pix', methods=['POST', 'OPTIONS'])
def gerar_pix():
    if request.method == 'OPTIONS': return '', 200
    dados = request.json
    
    email = dados.get('email')
    valor = float(dados.get('valor', 2.00))
    id_produto = dados.get('id_produto', 'produto_dia1')

    dados_pagamento = {
        "transaction_amount": valor,
        "description": f"A2X Pay - {id_produto}",
        "payment_method_id": "pix",
        "external_reference": id_produto, # Envia o ID do produto para o Webhook capturar depois
        "payer": {"email": email}
    }

    try:
        resposta = sdk.payment().create(dados_pagamento)
        pagamento = resposta.get("response", {})
        
        if "point_of_interaction" in pagamento:
            payment_id = str(pagamento["id"])
            transaction_data = pagamento["point_of_interaction"]["transaction_data"]
            
            # Registra a intenção de transação como pendente no banco
            try:
                supabase.table('transactions').insert({
                    "id": payment_id,
                    "user_email": email,
                    "product_id": id_produto,
                    "amount": valor,
                    "status": "pending"
                }).execute()
            except Exception as e:
                print(f"Aviso: Tabela 'transactions' ainda não criada ou configurada: {str(e)}")
            
            return jsonify({
                "sucesso": True,
                "id_pagamento": payment_id,
                "qr_code_base64": transaction_data["qr_code_base64"],
                "qr_code_copia_cola": transaction_data["qr_code"]
            })
        return jsonify({"sucesso": False, "detalhes": pagamento}), 400
    except Exception as e:
        return jsonify({"sucesso": False, "erro": str(e)}), 500

# 3. ROTA PARA O FRONT-END INSTANTÂNEO CHECAR STATUS DO PAGAMENTO
@app.route('/status-pagamento/<payment_id>', methods=['GET'])
def status_pagamento(payment_id):
    try:
        res = supabase.table("transactions").select("status").eq("id", payment_id).execute()
        if res.data:
            return jsonify({"status": res.data[0]["status"]})
        return jsonify({"status": "pending"})
    except:
        return jsonify({"status": "pending"})

# 4. ROTA WEBHOOK (BLINDADA PARA PRODUTOS E SKINS)
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    payment_id = None
    
    # Captura o ID independente se a chamada for do Webhook V1 ou V2 do Mercado Pago
    if data.get('type') == 'payment':
        payment_id = data.get('data', {}).get('id')
    elif data.get('action') == 'payment.updated':
        payment_id = data.get('data', {}).get('id')

    if payment_id:
        try:
            payment = sdk.payment().get(payment_id).get('response')
            
            if payment and payment.get('status') == 'approved':
                valor_pago = float(payment['transaction_amount'])
                
                # 1. Atualiza o montante global arrecadado
                try:
                    atual = supabase.table('campanha_stats').select('total_arrecadado').eq('id', 1).single().execute().data['total_arrecadado']
                    supabase.table('campanha_stats').update({'total_arrecadado': float(atual) + valor_pago}).eq('id', 1).execute()
                except:
                    pass
                
                # 2. Atualiza o status na tabela transactions
                try:
                    trans = supabase.table("transactions").update({"status": "approved"}).eq("id", payment_id).execute()
                    if trans.data:
                        email_cliente = trans.data[0]["user_email"]
                        
                        # 3. Garante a criação do usuário e geração da chave de acesso curta
                        user_check = supabase.table("users").select("*").eq("email", email_cliente).execute()
                        if not user_check.data:
                            nova_chave = gerar_chave_vip()
                            supabase.table("users").insert({
                                "email": email_cliente,
                                "access_key": nova_chave
                            }).execute()
                except:
                    pass
        except Exception as e:
            print(f"Erro processando webhook: {str(e)}")
            
    return '', 200

if __name__ == '__main__':
    app.run()
