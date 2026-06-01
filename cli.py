import argparse
import sys
from pathlib import Path
from card_merger import DeckMerger, CardError

def main():
    """
    Punkt wejścia (CLI) dla aplikacji łączącej karty do PDF.
    Przetwarza argumenty wiersza poleceń i odpytuje klasę logiki DeckMerger.
    """
    parser = argparse.ArgumentParser(
        description="Skrypt łączący pliki graficzne PNG kart w wielostronicowy plik PDF z uwzględnieniem duplikatów i rewersów."
    )
    parser.add_argument(
        "-i", "--input", 
        type=str, 
        default=".", 
        help="Katalog wejściowy z plikami kart .png (domyślnie obecny katalog)."
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="output.pdf", 
        help="Ścieżka do pliku wyjściowego PDF (domyślnie output.pdf)."
    )
    
    args = parser.parse_args()
    input_dir = Path(args.input).resolve()
    
    print(f"Skanowanie katalogu: {input_dir} ...")
    merger = DeckMerger(args.input)
    
    try:
        # Analiza i walidacja zawartości przed stworzeniem pliku PDF
        merger.parse_directory()
        
        cards_found = len(merger.cards)
        print(f"Znaleziono {cards_found} unikalnych kart do przetworzenia.")
        
        if merger.global_back:
            print(f"Znaleziono domyślny rewers globalny: {merger.global_back.name}")
        else:
            print("Nie znaleziono domyślnego rewersu globalnego.")
            
        if cards_found > 0:
            print(f"Generowanie sekwencji stron i tworzenie PDF: {args.output}...")
            
            # Generujemy PDF i odbieramy szczegółowe statystyki z DeckMergera
            stats = merger.generate_pdf(args.output)
            
            # Wyświetlanie czytelnego raportu końcowego
            print("\nZakończono sukcesem! Plik PDF został poprawnie utworzony.")
            print("=" * 50)
            print("                PODSUMOWANIE                ")
            print("=" * 50)
            print(f"📄 Plik wyjściowy           : {stats['output_path']}")
            print(f"📑 Sumaryczna liczba stron  : {stats['total_pages']}")
            print(f"🃏 Ilość unikalnych kart    : {stats['unique_cards']}")
            
            repeated = stats['repeated_cards']
            if repeated:
                print(f"\n🔁 Karty powielone ({len(repeated)} pozycji):")
                for c in repeated:
                    print(f"   - {c.base_name} (ilość kopii w talii: {c.qty})")
            else:
                print("\n🔁 Karty powielone: brak")
                
            skipped = stats['skipped_files']
            if skipped:
                print(f"\n🚫 Pominięte pliki ({len(skipped)} plików):")
                for s in skipped:
                    print(f"   - {s}")
            else:
                print("\n🚫 Pominięte pliki: brak")
                
            print("=" * 50)
            
        else:
            print("Brak odpowiednich kart do przetworzenia. Zakończono bez modyfikacji.")
            sys.exit(0)
            
    except CardError as e:
        print(f"\n[BŁĄD PRZETWARZANIA]: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[NIEOCZEKIWANY BŁĄD]: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
