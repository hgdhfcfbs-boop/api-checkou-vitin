from flask import Flask, request, jsonify
from flask_cors import CORS
import mercadopago
import os
from dotenv import load_dotenv

# 1. Abre o cofre e conecta no Mercado Pago
load_dotenv()
token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
sdk = mercadopago.SDK(token)

# 2. Inicia o servidor Flask
app = Flask(__name__)
CORS(app) # Isso permite que o HTML converse com o Python em paz

# 3. Cria a rota que vai gerar o Pix
@app.route('/gerar-pix', methods=['POST'])
def gerar_pix():
    dados = request.json
    valor = float(dados.get('valor', 2.00))

    dados_pagamento = {
        "transaction_amount": valor,
        "description": "Teste Beta - Checkout VIP",
        "payment_method_id": "pix",
        "payer": {
            "email": "teste@checkout.com"
        }
    }

    resposta = sdk.payment().create(dados_pagamento)
    pagamento = resposta["response"]

    if "point_of_interaction" in pagamento:
        transaction_data = pagamento["point_of_interaction"]["transaction_data"]
        return jsonify({
            "sucesso": True,
            "qr_code_base64": transaction_data["qr_code_base64"],
            "qr_code_copia_cola": transaction_data["qr_code"]
        })
    else:
        return jsonify({"sucesso": False}), 400

# 4. Liga a máquina
if __name__ == '__main__':
    print("🚀 Servidor Pix rodando nas sombras... (Porta 5000)")
    app.run(port=5000)