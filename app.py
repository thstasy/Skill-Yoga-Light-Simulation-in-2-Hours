import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for Matplotlib

from flask import Flask, request, jsonify
from flask_cors import CORS
import matplotlib.pyplot as plt
import numpy as np
import io
import base64

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests


def simulate_tissue_layers(layers, wavelength):
    """
    Simulates light scattering for layered tissue.
    """
    depth = []
    intensity = []
    current_depth = 0

    for layer in layers:
        thickness = layer['thickness']
        absorption_coeff = layer['absorption_coeff']
        scattering_coeff = layer['scattering_coeff']
        anisotropy = layer['anisotropy']

        μs_prime = scattering_coeff * (1 - anisotropy)
        μ_total = absorption_coeff + μs_prime

        layer_depth = np.linspace(current_depth, current_depth + thickness, 100)
        layer_intensity = np.exp(-μ_total * (layer_depth - current_depth))

        depth.extend(layer_depth)
        intensity.extend(layer_intensity)
        current_depth += thickness

    return depth, intensity


@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>OCT Simulation</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            #wavelength-slider {
                width: 100%;
                background: linear-gradient(to right, violet, indigo, blue, green, yellow, orange, red);
                border-radius: 5px;
                height: 15px;
                appearance: none;
                outline: none;
                cursor: pointer;
            }
            #wavelength-slider::-webkit-slider-thumb {
                appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: black;
                cursor: pointer;
            }
            input[type="number"] {
                width: 250px;
                padding: 5px;
                font-size: 14px;
                margin: 5px 0;
            }
        </style>
        <script>
            let layerCount = 1;

            function addLayer() {
                layerCount++;
                const layersSection = document.getElementById('layers-section');

                const layerDiv = document.createElement('div');
                layerDiv.innerHTML = `
                    <label>Layer ${layerCount}:</label>
                    <input type="number" name="thickness_${layerCount}" placeholder="Thickness (0.1 - 5 mm)" step="0.1" min="0.1" max="5">
                    <input type="number" name="absorption_${layerCount}" placeholder="Absorption Coeff (0 - 1 mm⁻¹)" step="0.01" min="0" max="1">
                    <input type="number" name="scattering_${layerCount}" placeholder="Scattering Coeff (0 - 50 mm⁻¹)" step="0.01" min="0" max="50">
                    <input type="number" name="anisotropy_${layerCount}" placeholder="Anisotropy (0 to 1)" step="0.01" min="0" max="1"><br>
                `;

                layersSection.appendChild(layerDiv);
            }

            function updateWavelengthLabel(value) {
                const label = document.getElementById('wavelength-label');
                label.innerText = `Wavelength: ${value} nm`;
            }

            async function runSimulation() {
                const form = document.getElementById('simulation-form');
                const formData = new FormData(form);

                const layers = [];
                for (let i = 1; i <= layerCount; i++) {
                    layers.push({
                        thickness: parseFloat(formData.get(`thickness_${i}`)),
                        absorption_coeff: parseFloat(formData.get(`absorption_${i}`)),
                        scattering_coeff: parseFloat(formData.get(`scattering_${i}`)),
                        anisotropy: parseFloat(formData.get(`anisotropy_${i}`))
                    });
                }

                const body = {
                    wavelength: parseInt(formData.get('wavelength')),
                    layers: layers
                };

                const response = await fetch('/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });

                const data = await response.json();

                if (response.ok) {
                    const plotResponse = await fetch('/plot', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    const plotData = await plotResponse.json();

                    if (plotResponse.ok) {
                        document.getElementById('plot-image').src = plotData.plot;
                    } else {
                        document.getElementById('results').innerText = `Error generating plot: ${plotData.error}`;
                    }
                } else {
                    document.getElementById('results').innerText = `Error: ${data.error}`;
                }
            }
        </script>
    </head>
    <body>
        <h1>OCT Simulation</h1>
        <form id="simulation-form">
            <label for="wavelength">Wavelength:</label>
            <input id="wavelength-slider" type="range" name="wavelength" min="400" max="800" step="1" 
                   value="800" oninput="updateWavelengthLabel(this.value)">
            <span id="wavelength-label">Wavelength: 800 nm</span><br>

            <div id="layers-section">
                <label>Layer 1:</label>
                <input type="number" name="thickness_1" placeholder="Thickness (0.1 - 5 mm)" step="0.1" min="0.1" max="5">
                <input type="number" name="absorption_1" placeholder="Absorption Coeff (0 - 1 mm⁻¹)" step="0.01" min="0" max="1">
                <input type="number" name="scattering_1" placeholder="Scattering Coeff (0 - 50 mm⁻¹)" step="0.01" min="0" max="50">
                <input type="number" name="anisotropy_1" placeholder="Anisotropy (0 to 1)" step="0.01" min="0" max="1"><br>
            </div>
            <button type="button" onclick="addLayer()">Add Layer</button><br>
            <button type="button" onclick="runSimulation()">Run Simulation</button>
        </form>
        <pre id="results"></pre>
        <img id="plot-image" src="" alt="Plot will appear here" style="max-width: 100%; margin-top: 20px;">
    </body>
    </html>
    '''


@app.route('/simulate', methods=['POST'])
def simulate():
    try:
        layers = request.json.get('layers', None)
        if not layers:
            return jsonify({'error': 'No layers provided'}), 400

        wavelength = int(request.json.get('wavelength', 800))
        depth, intensity = simulate_tissue_layers(layers, wavelength)

        return jsonify({'depth': depth, 'intensity': intensity})

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/plot', methods=['POST'])
def plot_simulation():
    try:
        data = request.json
        depth = data.get('depth')
        intensity = data.get('intensity')

        if not depth or not intensity:
            return jsonify({'error': 'Depth and Intensity data are required'}), 400

        plt.figure(figsize=(8, 5))
        plt.plot(depth, intensity, label="Intensity vs Depth")
        plt.xlabel("Depth (mm)")
        plt.ylabel("Intensity")
        plt.title("OCT Simulation Results")
        plt.legend()
        plt.grid()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plot_data = base64.b64encode(buf.getvalue()).decode()
        buf.close()

        return jsonify({'plot': f"data:image/png;base64,{plot_data}"})

    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True)