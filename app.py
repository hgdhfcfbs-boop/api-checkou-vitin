from flask import Flask, request, jsonify
from flask_cors import CORS
import mercadopago
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")

# Aviso de segurança no log do Render caso o token não seja encontrado
if not token:
    print("ALERTA CRÍTICO: Token do Mercado Pago não encontrado!")

sdk = mercadopago.SDK(token)

app = Flask(__name__)
# Libera o acesso para o seu Netlify se comunicar com o Render
CORS(app, resources={r"/*": {"origins": "*"}}) 

@app.route('/gerar-pix', methods=['POST', 'OPTIONS'])
def gerar_pix():
    # Responde à verificação de segurança do navegador
    if request.method == 'OPTIONS':
        return '', 200
        
    dados = request.json
    print(f"[DEBUG] Dados recebidos do site: {dados}") # Vai aparecer no Log do Render
    
    valor = float(dados.get('valor', 2.00))

    # Pacote de dados exigido pelo Mercado Pago
    dados_pagamento = {
        "transaction_amount": valor,
        "description": "Checkout VIP - Vitin",
        "payment_method_id": "pix",
        "payer": {
            "email": "cliente@vitin.com",
            "first_name": "Cliente",
            "last_name": "Vip"
        }
    }

    try:
        # Envia para o banco
        resposta = sdk.payment().create(dados_pagamento)
        pagamento = resposta.get("response", {})
        
        # Isso vai imprimir a resposta EXATA do Mercado Pago no log do Render
        print(f"[DEBUG] Resposta do Mercado Pago: {pagamento}") 
        
        # Se deu tudo certo, pega o QR Code
        if "point_of_interaction" in pagamento:
            transaction_data = pagamento["point_of_interaction"]["transaction_data"]
            return jsonify({
                "sucesso": True,
                "qr_code_base64": transaction_data["qr_code_base64"],
                "qr_code_copia_cola": transaction_data["qr_code"]
            })
        else:
            # Se o Mercado Pago recusar, agora sabemos o porquê!
            return jsonify({
                "sucesso": False, 
                "erro": "O Mercado Pago recusou a transação.",
                "detalhes": pagamento 
            }), 400
            
    except Exception as e:
        print(f"[ERRO CRÍTICO] Falha no código: {str(e)}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500

if __name__ == '__main__':
    app.run()
