from flask import Flask, request, jsonify
from flask_cors import CORS
import mercadopago
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
# NOVAS VARIÁVEIS
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

sdk = mercadopago.SDK(token)
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) 

# 1. ROTA PARA LER O PROGRESSO
@app.route('/progresso-atual', methods=['GET'])
def progresso():
    try:
        # Busca o valor total no Supabase
        response = supabase.table('campanha_stats').select('total_arrecadado').eq('id', 1).single().execute()
        return jsonify({"total": float(response.data['total_arrecadado'])})
    except:
        return jsonify({"total": 0.00})

# 2. ROTA DE GERAR PIX (SUA ROTA MANTIDA)
@app.route('/gerar-pix', methods=['POST', 'OPTIONS'])
def gerar_pix():
    if request.method == 'OPTIONS': return '', 200
    dados = request.json
    valor = float(dados.get('valor', 2.00))

    dados_pagamento = {
        "transaction_amount": valor,
        "description": "Checkout VIP - Vitin",
        "payment_method_id": "pix",
        "payer": {"email": "cliente@vitin.com"}
    }

    try:
        resposta = sdk.payment().create(dados_pagamento)
        pagamento = resposta.get("response", {})
        
        if "point_of_interaction" in pagamento:
            transaction_data = pagamento["point_of_interaction"]["transaction_data"]
            return jsonify({
                "sucesso": True,
                "qr_code_base64": transaction_data["qr_code_base64"],
                "qr_code_copia_cola": transaction_data["qr_code"]
            })
        return jsonify({"sucesso": False, "detalhes": pagamento}), 400
    except Exception as e:
        return jsonify({"sucesso": False, "erro": str(e)}), 500

# 3. ROTA WEBHOOK (O SEGREDO DO "JÁ ERA")
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get('type') == 'payment':
        payment_id = data.get('data', {}).get('id')
        payment = sdk.payment().get(payment_id).get('response')
        
        if payment['status'] == 'approved':
            valor_pago = float(payment['transaction_amount'])
            
            # Atualiza no Supabase
            atual = supabase.table('campanha_stats').select('total_arrecadado').eq('id', 1).single().execute().data['total_arrecadado']
            supabase.table('campanha_stats').update({'total_arrecadado': float(atual) + valor_pago}).eq('id', 1).execute()
            
    return '', 200

if __name__ == '__main__':
    app.run()
