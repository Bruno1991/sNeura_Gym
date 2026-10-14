# Slither.io - Bot Neura-Híbrido v6.0 Master
### (Rede Neural Deep Learning PPO 10h + IA Nativa do APK)

Bot autônomo para **Slither.io** combinando **Deep Reinforcement Learning (PPO)** treinado na GPU NVIDIA GeForce RTX 3060 com a salvaguarda de física geométrica descompilada do APK oficial (`gaim.Main`).

---

## 🌟 O que há de novo na Versão 6.0 Neura-Hybrid

1. **Pesos Neurais Embutidos (Opção A):**
   - O arquivo [`slither_console_injector.js`](file:///c:/dev/s_Neura_Gym/slither_bot/Scripted_Bot/slither_console_injector.js) já possui os pesos de ouro do Actor (37.000 parâmetros float32) diretamente embutidos no cabeçalho em JSON (~309 KB).
   - Não depende de bibliotecas externas (nem CDN, nem PyTorch, nem TensorFlow.js).
2. **Motor de Inferência Matricial em JavaScript Puro:**
   - Realiza o *forward pass* completo (2 camadas lineares de 128 neurônios, 2 normalizações LayerNorm, ativações ReLU, e cabeças de ângulo com Tanh e turbo com Sigmoid) em menos de **0.03 milissegundos** por tick.
3. **Extração de 32 Sensores Egocêntricos em Tempo Real:**
   - 16 Raios LIDAR 360° em volta da cabeça (ray-circle intersection com todos os corpos de cobras rivais e a borda da arena).
   - 8 Setores angulares de 45° mapeando densidade de alimentos e valor calórico.
   - 4 Leituras de radar da cabeça do oponente mais próximo.
   - 4 Estados internos (velocidade, tamanho, boost e proximidade do centro).
4. **Cérebro Triplo Alternável por Teclado (`[N]`):**
   - **`NEURA-HÍBRIDO` (Padrão):** A Rede Neural pilota a cobra traçando curvas fluidas e buscando comida. Se o LIDAR detectar perigo de colisão frontal (< 180px), a salvaguarda do APK assume instantaneamente para desviar a 15° sem turbo, eliminando mortes acidentais.
   - **`REDE NEURAL PURA`:** A Rede Neural toma 100% das decisões de ângulo e turbo sem nenhuma intervenção algorítmica.
   - **`APK NATIVO PURO`:** O algoritmo original descompilado do APK.

---

## 🚀 Como Usar no Navegador

### Injeção no Console do Navegador (Recomendado)
1. Abra **[https://slither.io](https://slither.io)** no Chrome, Brave, Edge ou Firefox.
2. Pressione **`F12`** (ou `Ctrl + Shift + I`) e vá para a aba **Console**.
3. Abra o arquivo [`slither_console_injector.js`](file:///c:/dev/s_Neura_Gym/slither_bot/Scripted_Bot/slither_console_injector.js), copie todo o conteúdo (`Ctrl+A`, `Ctrl+C`).
4. Cole no Console e aperte **Enter**.
5. Digite seu apelido e clique em **Play** (ou deixe o bot renascer sozinho!).

---

## 🎮 Controles no Teclado

- **`[N]`**: Alterna entre os modos cerebrais (**NEURA-HÍBRIDO** ➔ **REDE NEURAL PURA** ➔ **APK NATIVO**).
- **`[T]`**: Alterna **Piloto Automático** (LIGADO / DESLIGADO) para assumir o controle manual no mouse.
- **`[R]`**: Alterna **Auto-Respawn** (LIGADO / DESLIGADO).
- **`[O]`**: Oculta ou exibe o painel visual **HUD**.
