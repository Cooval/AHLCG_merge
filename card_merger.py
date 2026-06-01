import os
import re
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
import img2pdf

# Wyciszamy spam z biblioteki img2pdf dotyczący przezroczystości (alpha channel)
logging.getLogger("img2pdf").setLevel(logging.ERROR)

def natural_sort_key(s: str) -> List[Any]:
    """
    Zwraca klucz do naturalnego sortowania stringów.
    Dzięki temu np. 'ahc001-9' będzie przed 'ahc001-10'.
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

class ProgressList(list):
    """Pomocnicza klasa dziedzicząca po liście, wyświetlająca wskaźnik postępu podczas iteracji."""
    def __iter__(self):
        total = len(self)
        for i, item in enumerate(super().__iter__(), 1):
            percent = (i / total) * 100
            # \r pozwala na nadpisywanie tej samej linii w konsoli
            print(f"\rPrzetwarzanie strony: {i}/{total} ({percent:.1f}%)", end="", flush=True)
            yield item

class CardError(Exception):
    """Wyjątek rzucany w przypadku błędów związanych z przetwarzaniem kart."""
    pass

class Card:
    """Reprezentacja pojedynczej karty posiadającej ewentualny front, back i zadaną ilość."""
    def __init__(self, base_name: str, qty: int = 1):
        self.base_name = base_name
        self.qty = qty
        self.front_path: Optional[Path] = None
        self.back_path: Optional[Path] = None

class DeckMerger:
    """
    Klasa odpowiedzialna za łączenie plików kart w sekwencję stron
    oraz generowanie z nich pliku PDF.
    """
    
    FILENAME_PATTERN = re.compile(r"^(.*?)(?:-x(\d+))?-([^.-]+)\.png$", re.IGNORECASE)
    
    FRONT_FLAGS = {"1", "a", "front"}
    BACK_FLAGS = {"2", "b", "back"}
    GLOBAL_BACK_NAMES = {"back.png", "_encounterback.png", "_playerback.png"}

    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.cards: Dict[str, Card] = {}
        self.global_back: Optional[Path] = None
        self.skipped_files: List[str] = []

    def parse_directory(self) -> None:
        if not self.input_dir.is_dir():
            raise CardError(f"Katalog wejściowy nie istnieje: {self.input_dir}")
            
        for file_path in self.input_dir.iterdir():
            if not file_path.is_file() or file_path.suffix.lower() != ".png":
                continue
            
            # Weryfikacja plików przestarzałych oznaczonych znacznikiem -OLD-
            if "-OLD-" in file_path.name.upper():
                self.skipped_files.append(file_path.name)
                continue
                
            if file_path.name.lower() in self.GLOBAL_BACK_NAMES:
                if not self.global_back:
                    self.global_back = file_path
                continue

            match = self.FILENAME_PATTERN.match(file_path.name)
            if not match:
                self.skipped_files.append(file_path.name)
                continue

            base_name, qty_str, side_flag = match.groups()
            qty = int(qty_str) if qty_str else 1
            side_flag = side_flag.lower()

            if base_name not in self.cards:
                self.cards[base_name] = Card(base_name, qty)
            
            card = self.cards[base_name]
            
            if qty > 1:
                card.qty = max(card.qty, qty)

            if side_flag in self.FRONT_FLAGS:
                card.front_path = file_path
            elif side_flag in self.BACK_FLAGS:
                card.back_path = file_path

    def build_page_sequence(self) -> List[str]:
        pages: List[str] = []
        sorted_cards = sorted(self.cards.values(), key=lambda c: natural_sort_key(c.base_name))
        
        for card in sorted_cards:
            if not card.front_path:
                raise CardError(f"Brakuje pliku frontu dla karty '{card.base_name}'.")
            
            back = card.back_path or self.global_back
            
            if not back:
                raise CardError(
                    f"Brakuje pliku tyłu dla karty '{card.base_name}' "
                    f"i nie znaleziono żadnego domyślnego rewersu w folderze {self.input_dir}."
                )
            
            for _ in range(card.qty):
                pages.append(str(card.front_path))
                pages.append(str(back))
                
        return pages

    def generate_pdf(self, output_path: str) -> Dict[str, Any]:
        pages = self.build_page_sequence()
        
        if not pages:
            raise CardError("Brak stron do wygenerowania. Upewnij się, że w folderze znajdują się pasujące pliki .png.")
            
        progress_pages = ProgressList(pages)
        pdf_bytes = img2pdf.convert(progress_pages)
        
        print("\nZapisywanie pliku PDF na dysk...", flush=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
            
        # Generowanie statystyk zwrotnych z wykonanej pracy
        repeated_cards = [c for c in self.cards.values() if c.qty > 1]
        
        return {
            "output_path": output_path,
            "total_pages": len(pages),
            "unique_cards": len(self.cards),
            "repeated_cards": repeated_cards,
            "skipped_files": self.skipped_files
        }
