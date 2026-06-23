from flask import Flask, request, jsonify
from flask_cors import CORS
import mercadopago
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
sdk = mercadopago.SDK(token)

app = Flask(__name__)
# Isso libera o acesso de qualquer site para o seu servidor
CORS(app, resources={r"/*": {"origins": "*"}}) 

@app.route('/gerar-pix', methods=['POST', 'OPTIONS'])
def gerar_pix():
    if request.method == 'OPTIONS':
        return '', 200
        
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
        pagamento = resposta["response"]
        
        if "point_of_interaction" in pagamento:
            transaction_data = pagamento["point_of_interaction"]["transaction_data"]
            return jsonify({
                "sucesso": True,
                "qr_code_base64": transaction_data["qr_code_base64"],
                "qr_code_copia_cola": transaction_data["qr_code"]
            })
    except Exception as e:
        return jsonify({"sucesso": False, "erro": str(e)}), 400
    
    return jsonify({"sucesso": False}), 400

if __name__ == '__main__':
    app.run()
