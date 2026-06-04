import os
import re
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import defaultdict
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
        self.skipped_old: List[Path] = []
        self.skipped_unmatched: List[Path] = []

    def parse_directory(self) -> None:
        if not self.input_dir.is_dir():
            raise CardError(f"Input directory does not exist: {self.input_dir}")
            
        for file_path in self.input_dir.iterdir():
            if not file_path.is_file() or file_path.suffix.lower() != ".png":
                continue
            
            # Verification of obsolete files marked with the -OLD- tag
            if "-OLD-" in file_path.name.upper():
                self.skipped_old.append(file_path)
                continue
                
            if file_path.name.lower() in self.GLOBAL_BACK_NAMES:
                if not self.global_back:
                    self.global_back = file_path
                continue

            # Also skip files starting with underscore explicitly so they don't become unmatched conflicts
            if file_path.name.startswith("_"):
                continue

            match = self.FILENAME_PATTERN.match(file_path.name)
            if not match:
                self.skipped_unmatched.append(file_path)
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

    def needs_global_back(self) -> bool:
        """Returns True if there is at least one card that requires a global back."""
        for card in self.cards.values():
            if not card.back_path:
                return True
        return False

    def get_back_candidates(self) -> List[str]:
        """Returns a list of filenames that are candidates for a global back."""
        candidates = []
        for file_path in self.input_dir.iterdir():
            if not file_path.is_file() or file_path.suffix.lower() != ".png":
                continue
            name = file_path.name
            if name.startswith("_") or "back" in name.lower():
                candidates.append(name)
        return candidates

    def get_conflicts(self) -> List[Dict[str, Any]]:
        """Returns a list of conflicts (alt cards, OLD cards, unmatched cards) that need user resolution."""
        conflicts = []
        
        # 1. Alt cards
        groups = defaultdict(list)
        for base_name, card in self.cards.items():
            norm = re.sub(r'(?i)alt', '', base_name)
            norm = re.sub(r'\s*\((?![0-9]+\)).*?\)', '', norm).strip()
            groups[norm].append(card)
            
        for norm, cards in groups.items():
            if len(cards) > 1:
                # We have multiple cards that map to the same normalized base name
                options = [{"filename": c.front_path.name, "label": c.base_name, "base_name": c.base_name} for c in cards if c.front_path]
                if len(options) > 1:
                    conflicts.append({
                        "id": f"alt_{norm}",
                        "type": "alt_conflict",
                        "description": f"Duplicate cards with the same number: '{norm}'",
                        "options": options
                    })
                    
        # 2. Skipped OLD
        for p in self.skipped_old:
            conflicts.append({
                "id": f"old_{p.name}",
                "type": "skipped_old",
                "description": f"Skipped OLD card: {p.name}",
                "options": [
                    {"filename": p.name, "label": "Include in print"}
                ]
            })
            
        # 3. Skipped Unmatched
        for p in self.skipped_unmatched:
            conflicts.append({
                "id": f"unmatched_{p.name}",
                "type": "skipped_unmatched",
                "description": f"Unrecognized file name: {p.name}",
                "options": [
                    {"filename": p.name, "label": "Include in print (will be added as front)"}
                ]
            })
            
        return conflicts

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
            
        # Define a fixed page layout of 2.74 x 3.74 inches (standard card size)
        # This completely ignores broken 72 DPI metadata from source images.
        page_width_pt = img2pdf.in_to_pt(2.74)
        page_height_pt = img2pdf.in_to_pt(3.74)
        
        layout_fun = img2pdf.get_layout_fun(
            pagesize=(page_width_pt, page_height_pt),
            fit=img2pdf.FitMode.into
        )
        
        # User requested TrimBox 61.2 x 88.4 mm perfectly centered.
        trim_width_pt = img2pdf.mm_to_pt(61.2)
        trim_height_pt = img2pdf.mm_to_pt(88.4)
        
        trim_margin_x = (page_width_pt - trim_width_pt) / 2.0
        trim_margin_y = (page_height_pt - trim_height_pt) / 2.0
        
        # img2pdf trimborder takes (margin_y, margin_x)
        trimborder = (trim_margin_y, trim_margin_x)
        
        pdf_bytes = img2pdf.convert(progress_pages, layout_fun=layout_fun, trimborder=trimborder)
        
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
            "skipped_files": [p.name for p in self.skipped_old + self.skipped_unmatched]
        }
        
        msg_done = f"Success! PDF generated with {stats['total_pages']} pages across {stats['unique_cards']} unique cards."
        if callback and not quiet:
            callback(msg_done)
        elif not quiet:
            print(msg_done)
            
        return stats
