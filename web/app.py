import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Pasta onde os arquivos .owl serão salvos (opcional)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'temp')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

# Rota OPCIONAL: Salva o arquivo .owl no servidor
@app.route('/upload-owl', methods=['POST'])
def upload_owl():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nome de arquivo vazio"}), 400
    
    if not file.filename.lower().endswith(('.owl', '.rdf', '.xml', '.rdfs')):
        return jsonify({"error": "Formato inválido. Envie .owl, .rdf, .xml ou .rdfs"}), 400

    save_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(save_path)
    
    return jsonify({"message": "Arquivo salvo com sucesso", "path": save_path}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)