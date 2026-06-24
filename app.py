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
# DICA: Troque o '*' pelo link do seu Netlify assim que possível para mais segurança
CORS(app, resources={r"/*": {"origins": "*"}}) 

# FUNÇÃO AUXILIAR PARA GERAR CHAVE
def gerar_chave_vip():
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"VTN-{chars}"

# 1. ROTA PARA LER O PROGRESSO
@app.route('/progresso-atual', methods=['GET'])
def progresso():
    try:
        response = supabase.table('campanha_stats').select('total_arrecadado').eq('id', 1).single().execute()
        return jsonify({"total": float(response.data['total_arrecadado'])})
    except:
        return jsonify({"total": 0.00})

# 2. ROTA DE GERAR PIX
@app.route('/gerar-pix', methods=['POST', 'OPTIONS'])
def gerar_pix():
    if request.method == 'OPTIONS': return '', 200
    dados = request.json
    valor = float(dados.get('valor', 2.00))
    email = dados.get('email', 'cliente@vitin.com') # Pega o email que o user digitou

    dados_pagamento = {
        "transaction_amount": valor,
        "description": "Checkout VIP - Vitin",
        "payment_method_id": "pix",
        "payer": {"email": email} # Agora usa o email real
    }

    try:
        resposta = sdk.payment().create(dados_pagamento)
        pagamento = resposta.get("response", {})
        
        if "point_of_interaction" in pagamento:
            transaction_data = pagamento["point_of_interaction"]["transaction_data"]
            return jsonify({
                "sucesso": True,
                "id_pagamento": pagamento["id"],
                "qr_code_base64": transaction_data["qr_code_base64"],
                "qr_code_copia_cola": transaction_data["qr_code"]
            })
        return jsonify({"sucesso": False, "detalhes": pagamento}), 400
    except Exception as e:
        return jsonify({"sucesso": False, "erro": str(e)}), 500

# 3. ROTA DE VALIDAÇÃO DE CHAVE (A MESTRA)
@app.route('/validar-chave', methods=['POST'])
def validar_chave():
    dados = request.json
    chave = dados.get('chave', '').upper().strip()
    
    if chave == "VTN-ADMIN":
        return jsonify({"sucesso": True, "tipo": "admin", "msg": "Acesso total liberado."})
    
    try:
        res = supabase.table("users").select("*").eq("access_key", chave).execute()
        if res.data:
            return jsonify({"sucesso": True, "tipo": "usuario", "email": res.data[0]["email"]})
        return jsonify({"sucesso": False, "msg": "Chave inválida."}), 404
    except Exception as e:
        return jsonify({"sucesso": False, "msg": str(e)}), 500

# 4. ROTA WEBHOOK
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get('type') == 'payment':
        payment_id = data.get('data', {}).get('id')
        payment = sdk.payment().get(payment_id).get('response')
        
        if payment['status'] == 'approved':
            valor_pago = float(payment['transaction_amount'])
            email_cliente = payment['payer']['email']
            
            # Atualiza no Supabase
            atual = supabase.table('campanha_stats').select('total_arrecadado').eq('id', 1).single().execute().data['total_arrecadado']
            supabase.table('campanha_stats').update({'total_arrecadado': float(atual) + valor_pago}).eq('id', 1).execute()
            
            # Gera chave pro usuário se ele não existir
            user_check = supabase.table("users").select("*").eq("email", email_cliente).execute()
            if not user_check.data:
                nova_chave = gerar_chave_vip()
                supabase.table("users").insert({"email": email_cliente, "access_key": nova_chave}).execute()
            
    return '', 200

if __name__ == '__main__':
    app.run()
