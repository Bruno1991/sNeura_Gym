import json

history_path = "C:/dev/s_Neura_Gym/chess_bot/Neural_Bot/checkpoints/bateria_50k_history.json"
with open(history_path, "r", encoding="utf-8") as f:
    data = json.load(f)

cycles = data.get("cycles", [])
if cycles:
    c = cycles[-1]
    t = c["total_completed_games"]
    w = c["global_neural_wins"]
    l = c["global_engine_wins"]
    dr = c["global_draws"]
    wr = c["neural_win_rate"]
    dr_rate = c["draw_rate"]
    loss_rate = (l / max(1, t)) * 100
    hours = c["total_elapsed_seconds"] / 3600.0
    loss = c["loss"]
    cycle = c["cycle"]
    score = ((w + 0.5 * dr) / t) * 100.0

    print("=" * 60)
    print("        RELATORIO DE PROGRESSO: BATERIA 50.000 PARTIDAS")
    print("=" * 60)
    print(f" [*] Partidas Jogadas  : {t:,} / 50.000 ({t/50000*100:.1f}%)")
    print(f" [*] Ciclo Atual       : {cycle} / 200")
    print(f" [*] Vitorias Neural   : {w:,} ({wr:.2f}%)")
    print(f" [*] Empates           : {dr:,} ({dr_rate:.2f}%)")
    print(f" [*] Derrotas          : {l:,} ({loss_rate:.2f}%)")
    print(f" [*] Score Global      : {score:.2f}%")
    print(f" [*] Loss AMP FP16     : {loss:.4f}")
    print(f" [*] Tempo Decorrido   : {hours:.2f} horas ({hours*60:.0f} min)")
    print(f" [*] No Ultimo Ciclo   : +{c['cycle_neural_wins']}V / +{c['cycle_draws']}E / +{c['cycle_engine_wins']}D em {c['cycle_time_seconds']:.1f}s")
    print("=" * 60)
