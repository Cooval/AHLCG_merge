import os
import re
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
import img2pdf

# Suppress spam from the img2pdf library regarding the alpha channel
logging.getLogger("img2pdf").setLevel(logging.ERROR)

def natural_sort_key(s: str) -> List[Any]:
    """
    Returns a key for natural sorting of strings.
    This ensures that e.g. 'ahc001-9' comes before 'ahc001-10'.
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

class ProgressList(list):
    """Helper class inheriting from list, displaying a progress indicator during iteration."""
    def __init__(self, iterable, quiet: bool = False, callback: Optional[Any] = None):
        super().__init__(iterable)
        self.quiet = quiet
        self.callback = callback

    def __iter__(self):
        total = len(self)
        for i, item in enumerate(super().__iter__(), 1):
            if not self.quiet:
                percent = (i / total) * 100
                msg = f"Processing page: {i}/{total} ({percent:.1f}%)"
                if self.callback:
                    self.callback(msg)
                else:
                    # \r allows overwriting the same line in the console
                    print(f"\r{msg}", end="", flush=True)
            yield item

class CardError(Exception):
    """Exception raised in case of errors related to card processing."""
    pass

class Card:
    """Representation of a single card having an optional front, back, and a given quantity."""
    def __init__(self, base_name: str, qty: int = 1):
        self.base_name = base_name
        self.qty = qty
        self.front_path: Optional[Path] = None
        self.back_path: Optional[Path] = None

class DeckMerger:
    """
    Class responsible for merging card files into a sequence of pages
    and generating a PDF file from them.
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
            raise CardError(f"Input directory does not exist: {self.input_dir}")
            
        for file_path in self.input_dir.iterdir():
            if not file_path.is_file() or file_path.suffix.lower() != ".png":
                continue
            
            # Verification of obsolete files marked with the -OLD- tag
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
                raise CardError(f"Front file missing for card '{card.base_name}'.")
            
            back = card.back_path or self.global_back
            
            if not back:
                raise CardError(
                    f"Back file missing for card '{card.base_name}' "
                    f"and no default card back found in folder {self.input_dir}."
                )
            
            for _ in range(card.qty):
                pages.append(str(card.front_path))
                pages.append(str(back))
                
        return pages

    def generate_pdf(self, output_path: str, quiet: bool = False, callback: Optional[Any] = None) -> Dict[str, Any]:
        pages = self.build_page_sequence()
        
        if not pages:
            raise CardError("No pages to generate. Make sure the folder contains matching .png files.")
            
        progress_pages = ProgressList(pages, quiet=quiet, callback=callback)
        
        if callback and not quiet:
            callback("Starting PDF generation with img2pdf...")
            
        pdf_bytes = img2pdf.convert(progress_pages)
        
        msg_saving = "Saving PDF file to disk..."
        if callback and not quiet:
            callback(msg_saving)
        elif not quiet:
            print(f"\n{msg_saving}", flush=True)
            
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
            
        # Generating summary statistics
        repeated_cards = [c for c in self.cards.values() if c.qty > 1]
        
        stats = {
            "output_path": output_path,
            "total_pages": len(pages),
            "unique_cards": len(self.cards),
            "repeated_cards": repeated_cards,
            "skipped_files": self.skipped_files
        }
        
        msg_done = f"Success! PDF generated with {stats['total_pages']} pages across {stats['unique_cards']} unique cards."
        if callback and not quiet:
            callback(msg_done)
        elif not quiet:
            print(msg_done)
            
        return stats
