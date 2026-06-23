import pandas as pd

kills    = pd.read_parquet(r"C:\Users\marce\Desktop\CSGO_Analytics\processed\kills.parquet")
grenades = pd.read_parquet(r"C:\Users\marce\Desktop\CSGO_Analytics\processed\grenades.parquet")

fl = grenades[grenades["nade"] == "Flash"]
print("Flash seconds sample:")
print(fl["seconds"].describe())
print(fl[["file","round","seconds"]].head(5))

print("\nKills seconds sample:")
print(kills["seconds"].describe())
print(kills[["file","round","seconds"]].head(5))