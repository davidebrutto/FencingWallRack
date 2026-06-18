from werkzeug.security import generate_password_hash

# Sostituisci con la password che desideri impostare
nuova_password = "federscherma"

# Genera l'hash con lo stesso algoritmo (PBKDF2 con SHA-256)
nuovo_hash = generate_password_hash(nuova_password, method='pbkdf2:sha256', salt_length=16)
print(nuovo_hash)
