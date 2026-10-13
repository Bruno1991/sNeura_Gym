# Slither.io - Bot Nativo APK (IA Descompilada do APK Oficial) - v4.0

Bot 100% autônomo para **Slither.io** construído com base na engenharia reversa do código-fonte nativo extraído do APK oficial (`gaim.Main`).

---

## 🚀 Como Usar no Navegador

### Opção 1: Injeção Direta no Console (Mais Rápido - 10 segundos)
1. Abra **[https://slither.io](https://slither.io)** no seu navegador (Chrome, Edge, Firefox, Brave, etc.).
2. Pressione **`F12`** (ou `Ctrl + Shift + I`) e vá para a aba **Console**.
3. Abra o arquivo [`slither_console_injector.js`](file:///c:/dev/s_Neura_Gym/slither_bot/Scripted_Bot/slither_console_injector.js), copie **todo** o conteúdo (`Ctrl+A`, `Ctrl+C`).
4. Cole no Console e aperte **Enter**.
5. Digite um apelido e clique em **Play** (ou deixe o bot renascer e jogar sozinho!).

### Opção 2: Extensão Tampermonkey / Violentmonkey (Automático)
1. Instale a extensão Tampermonkey ou Violentmonkey no seu navegador.
2. Crie um novo script e cole o conteúdo de [`slither_apk_bot.user.js`](file:///c:/dev/s_Neura_Gym/slither_bot/Scripted_Bot/slither_apk_bot.user.js).
3. Salve. O bot carregará automaticamente em qualquer aba do `slither.io`.

---

## 🎮 Controles e Atalhos no Jogo

- **`[T]`**: Alterna **Piloto Automático** (LIGADO / DESLIGADO). Permite que você assuma o controle do mouse a qualquer momento!
- **`[R]`**: Alterna **Auto-Respawn** (LIGADO / DESLIGADO). Quando ativo, o bot renasce sozinho 1.5s após morrer.
- **`[O]`**: Alterna visibilidade do painel **HUD** na tela.

---

## 🧠 Arquitetura da IA (100% Fiel ao APK `gaim.Main`)

| Comportamento | Linhas do APK | Descrição Técnica |
|---|---|---|
| **Métrica de Chebyshev** | l. 11059-11083 | Distância calculada como `max(\|dx\|, \|dy\|)` para máxima precisão de colisão. |
| **Evitação Defensiva (`avpo`)** | l. 11087-11210 | Detecta obstáculos e aplica desvio tangencial de **±15°** (`±0.26 rad`). |
| **Alternância Direcional** | l. 11100-11114 | Alterna o giro defensivo (horário / anti-horário) a cada **2000 ms**. |
| **Ataque Predatório (Lead 95px)** | l. 11163-11214 | Mira **95 pixels à frente** da cabeça do oponente acionando turbo com predição balística. |
| **Forrageamento de Comida** | l. 11115-11162 | Varre presas luminosas e comida ao redor, priorizando os pontos de maior massa. |
| **Borda da Arena Centralizada** | Engine do Slither | Respeita o centro do mapa em `(grd, grd)` com margem de segurança de retorno. |
| **Isolamento de Mouse** | Injector v4.0 | Impede que movimentos ou repouso do cursor físico briguem com o vetor do bot. |

---

## 🧪 Validação em Navegador Headless

O bot foi extensivamente validado e estressado em Chromium Headless com Playwright diretamente contra os servidores oficiais do `slither.io`:
- **Direção e Ângulos:** Resposta instantânea de manobra em 360° em todos os ticks de física (30 FPS).
- **Sobrevivência:** Evasões defensivas confirmadas contra cobras rivais e crescimento de score verificado.
- **Auto-Respawn:** Múltiplas partidas jogadas em sequência ininterrupta de forma 100% autônoma.
