# AHLCG Merge

Skrypt w języku Python do automatycznego łączenia i przygotowywania plików graficznych PNG z kartami (fronty i rewersy) do wielostronicowego pliku PDF z użyciem kompresji bezstratnej (FlateDecode).

Projekt został stworzony z myślą o przygotowywaniu fanowskich dodatków, zachowując bezstratną jakość i elastyczność względem nietypowego nazewnictwa.

## Funkcje
- **Impozycja**: Automatyczne mapowanie frontu z odpowiednim rewersem.
- **Rewersy Globalne**: Sprytne odnajdywanie globalnych tyłów (`back.png`, `_encounterback.png`, `_playerback.png`) jeśli karta nie posiada własnego rewersu.
- **Obsługa duplikatów**: Jeśli na karcie znajduje się oznaczenie ilości (np. `-x3`), skrypt automatycznie utworzy w PDF odpowiednią liczbę naprzemiennych sekwencji dla tej karty.
- **Filtrowanie**: Automatyczne pomijanie kart zagnieżdżonych jako `-OLD-`.
- **Sortowanie naturalne**: Prawidłowe sortowanie plików projektów zawierających liczby (np. `ahc001-9` i `ahc001-10`).
- **Bezstratna kompresja**: Wykorzystuje potężną bibliotekę `img2pdf` w celu bezpośredniego wstrzykiwania obrazów do kontenera PDF unikając ubytków graficznych rekompresji.

## Instalacja

1. Pobierz repozytorium.
2. (Opcjonalne) Utwórz środowisko wirtualne:
   ```bash
   python -m venv .venv
   ```
   **Aktywacja w systemie Windows:**
   ```bash
   .venv\Scripts\activate
   ```
3. Zainstaluj biblioteki:
   ```bash
   pip install -r requirements.txt
   ```

## Sposób użycia

Skrypt najlepiej uruchomić z poziomu wiersza poleceń w folderze, w którym znajdują się wyeksportowane karty. Domyślnie przeszukuje folder w którym wywołałeś polecenie.

```bash
python cli.py -i "." -o "GotoweKarty.pdf"
```

Dostępne flagi:
- `-i` lub `--input` : folder z plikami kart .png (domyślnie obecny katalog)
- `-o` lub `--output` : nazwa/ścieżka tworzonego pliku PDF (domyślnie `output.pdf`)
