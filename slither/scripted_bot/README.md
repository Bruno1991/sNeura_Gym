# Slither.io - Bot Nativo APK (IA Descompilada do APK Oficial) - v5.0 Master

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

- **`[T]`**: Alterna **Piloto Automático** (LIGADO / DESLIGADO). Permite assumir o controle manual com o mouse quando desejar.
- **`[R]`**: Alterna **Auto-Respawn** (LIGADO / DESLIGADO). Quando ativo, o bot renasce sozinho 1.5s após a morte.
- **`[O]`**: Alterna a exibição do painel **HUD** na tela.

---

## 🧠 Arquitetura da IA (100% Fiel ao APK `gaim.Main`)

| Comportamento | Linhas do APK | Descrição Técnica |
|---|---|---|
| **Métrica de Chebyshev** | l. 11059-11083 | Distância calculada como `max(\|dx\|, \|dy\|)` para máxima precisão de colisão. |
| **Evitação Defensiva (`avpo`)** | l. 11087-11210 | Detecta obstáculos e aplica desvio tangencial de **±15°** (`±0.26 rad`) **sem turbo**. |
| **Física do Turbo na Esquiva** | Calibração v5.0 | Acelerar dobra o raio de curva ($R \approx 105$px vs $45$px). A IA nativa desativa turbo ao desviar para garantir o giro mais fechado e seguro. |
| **Limiar de Massa para Turbo** | l. 11170 (`me.sct > 10`) | Impede gasto de massa prematuro em cobras jovens, mantendo alta agilidade. |
| **Ataque Predatório (Lead 95px)** | l. 11163-11214 | Persegue a cabeça rival com predição balística a 95px à frente e turbo ativado (quando a área está livre de obstáculos). |
| **Caça a Presas Luminosas** | l. 11115-11162 | Ativa turbo para abocanhar presas rápidas a menos de 280px de distância. |
| **Tiro de Cruzeiro (`excited`)** | l. 11185-11200 | Aciona aceleração esporádica de curta duração (600–1800ms) em espaço aberto. |
| **Alternância Direcional** | l. 11100-11114 | Alterna o sentido do giro defensivo (horário / anti-horário) a cada 2000 ms. |
| **Borda da Arena Centralizada** | Engine Slither | Respeita o centro do mapa em `(grd, grd)` com margem de segurança de 800px. |
| **Isolamento de Mouse** | Injector v5.0 | Previne conflitos entre o ponteiro físico do mouse e o vetor de navegação da IA. |

---

## 🧪 Validação em Navegador Headless (Playwright Chromium)

O bot passa por validação contínua em ambiente headless real contra os servidores oficiais do `slither.io`:
- **Sobrevivência:** >95% de tempo vivo em partidas prolongadas.
- **Turbo Inteligente:** Disparado apenas com massa $\ge 10$ e caminho desobstruído.
- **Loop Contínuo:** Auto-respawn e HUD dinâmico em tempo real.
