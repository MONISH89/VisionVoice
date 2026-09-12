import os
import time
import json
import hashlib
import logging
import config

logger = logging.getLogger("VisionVoice.Memory")

class BookMemoryManager:
    """
    Book Memory and Persistent Reading Progress Manager for VisionVoice.
    Maintains:
      - identified_book: ID and metadata of recognized physical book
      - current_page / current_progress: exact reading position (page & sentence index)
      - last_processed_page: latest page processed through the CV/OCR pipeline

    CRITICAL RESILIENCE ARCHITECTURE:
    Book identification and progress persistence are secondary features.
    If book identification or memory storage fails (e.g. minimal text, corrupted JSON,
    or disk I/O errors), the system degrades gracefully and never crashes or stops
    the core OCR -> Language Detection -> Reading pipeline.
    """

    def __init__(self):
        self.books_dir = getattr(config, "BOOKS_DIR", os.path.join(getattr(config, "DATA_DIR", "."), "books"))
        self.sessions_dir = getattr(config, "SESSIONS_DIR", os.path.join(getattr(config, "DATA_DIR", "."), "sessions"))
        self.current_session_file = os.path.join(self.sessions_dir, "current_session.json")

        self.current_book_id = None
        self.current_page_num = 1
        self.last_processed_page = 1
        self.last_processed_image_path = None
        self._current_sentence_index = 0
        self.preferred_language = getattr(config, "DEFAULT_LANGUAGE", "en")
        self.reading_mode = getattr(config, "READING_MODE_PREFERRED", "preferred")

        # Ensure storage directories exist safely
        for d in [self.books_dir, self.sessions_dir]:
            try:
                os.makedirs(d, exist_ok=True)
            except Exception as e:
                logger.warning(f"Could not create memory directory '{d}': {e}")

        self._load_current_session()

    @property
    def identified_book(self):
        """Returns the ID of currently identified book, or None if unidentified."""
        return self.current_book_id

    @property
    def current_page(self):
        """Returns the active reading page number."""
        return self.current_page_num

    @current_page.setter
    def current_page(self, val):
        self.current_page_num = max(1, val)

    @property
    def current_sentence_index(self):
        return self._current_sentence_index

    @current_sentence_index.setter
    def current_sentence_index(self, val):
        self._current_sentence_index = max(0, val)

    @property
    def current_sentence_idx(self):
        return self._current_sentence_index

    @current_sentence_idx.setter
    def current_sentence_idx(self, val):
        self._current_sentence_index = max(0, val)

    @property
    def current_progress(self):
        """Returns dictionary describing active reading progress."""
        return {
            "identified_book": self.current_book_id,
            "book_id": self.current_book_id,
            "current_page": self.current_page_num,
            "current_sentence_index": self._current_sentence_index,
            "last_processed_page": self.last_processed_page,
            "preferred_language": self.preferred_language,
            "reading_mode": self.reading_mode
        }

    def record_processed_page(self, page_num, image_path=None):
        """
        Records the last processed page index and optional image artifact path.
        Safe against non-integer inputs or I/O exceptions.
        """
        try:
            self.last_processed_page = max(1, int(page_num))
            self.last_processed_image_path = image_path
            logger.debug(f"Recorded last processed page: {self.last_processed_page}")
        except Exception as e:
            logger.warning(f"Failed to record last processed page ({e}). Degrading gracefully.")

    def _load_current_session(self):
        """Loads last saved session state from JSON file with safe error handling."""
        if not os.path.exists(self.current_session_file):
            return

        try:
            with open(self.current_session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.current_book_id = data.get("current_book_id")
                self.current_page_num = data.get("current_page_num", 1)
                self.last_processed_page = data.get("last_processed_page", self.current_page_num)
                self.current_sentence_idx = data.get("current_sentence_idx", 0)
                self.preferred_language = data.get("preferred_language", getattr(config, "DEFAULT_LANGUAGE", "en"))
                self.reading_mode = data.get("reading_mode", getattr(config, "READING_MODE_PREFERRED", "preferred"))
            logger.info(f"Loaded existing session: book_id={self.current_book_id}, page={self.current_page_num}, last_processed={self.last_processed_page}, sentence={self.current_sentence_idx}")
        except Exception as e:
            logger.warning(f"Error reading session state file ({e}). Starting clean session.")

    def save_session(self):
        """Persists current active session state to disk safely."""
        session_data = {
            "current_book_id": self.current_book_id,
            "current_page_num": self.current_page_num,
            "last_processed_page": self.last_processed_page,
            "current_sentence_idx": self.current_sentence_idx,
            "preferred_language": self.preferred_language,
            "reading_mode": self.reading_mode,
            "timestamp": time.time()
        }
        try:
            with open(self.current_session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2)
            logger.debug(f"Saved active session state for book '{self.current_book_id}'")
        except Exception as e:
            logger.warning(f"Failed to persist session state ({e}). Gracefully continuing.")

    def generate_fingerprint(self, text):
        """
        Generates a deterministic hash signature from extracted page text.
        Extracts key word tokens to allow fuzzy book matching even if OCR has minor typos.
        """
        if not text or not str(text).strip():
            return ""
        try:
            words = [w.lower() for w in str(text).split() if len(w) > 3]
            sample = " ".join(words[:25])
            if not sample:
                sample = str(text).strip()[:50]
            return hashlib.md5(sample.encode("utf-8")).hexdigest()
        except Exception as e:
            logger.debug(f"Fingerprint generation error: {e}")
            return ""

    def identify_or_create_book(self, text, detected_lang="en"):
        """
        Checks extracted page text against saved book records.
        If identification encounters an issue (minimal text, disk failure),
        gracefully returns safe fallback metadata so reading continues uninterrupted.

        Returns:
            dict with keys:
                - 'book_id': str
                - 'is_new_book': bool
                - 'last_page': int
                - 'last_sentence_idx': int
                - 'book_data': dict
        """
        # Fallback for empty or minimal text
        if not text or len(str(text).strip()) < 10:
            if self.current_book_id:
                return self._get_existing_book_result(self.current_book_id, False)
            return {
                "book_id": None,
                "is_new_book": False,
                "last_page": self.current_page_num,
                "last_sentence_idx": 0,
                "book_data": {}
            }

        try:
            fingerprint = self.generate_fingerprint(text)
            all_books = self._list_all_books()

            # 1. Exact Fingerprint Match
            matched_book_id = None
            for b_id, b_data in all_books.items():
                fps = b_data.get("fingerprints", [])
                if fingerprint and fingerprint in fps:
                    matched_book_id = b_id
                    logger.info(f"Exact fingerprint match found for Book ID: '{matched_book_id}'")
                    break

            # 2. Fuzzy Keyword Overlap Match
            if not matched_book_id:
                first_words = set([w.lower() for w in text.split()[:15] if len(w) > 3])
                if len(first_words) >= 4:
                    for b_id, b_data in all_books.items():
                        title_words = set(b_data.get("sample_words", []))
                        if len(first_words.intersection(title_words)) >= 4:
                            matched_book_id = b_id
                            logger.info(f"Fuzzy signature match found for Book ID: '{matched_book_id}'")
                            break

            # 3. Existing Book Matched
            if matched_book_id:
                self.current_book_id = matched_book_id
                book_file = os.path.join(self.books_dir, f"{matched_book_id}.json")
                book_data = {}
                try:
                    if os.path.exists(book_file):
                        with open(book_file, "r", encoding="utf-8") as f:
                            book_data = json.load(f)

                        # Update fingerprint list
                        if fingerprint and fingerprint not in book_data.get("fingerprints", []):
                            book_data.setdefault("fingerprints", []).append(fingerprint)
                            with open(book_file, "w", encoding="utf-8") as f:
                                json.dump(book_data, f, indent=2)
                except Exception as e:
                    logger.warning(f"Error accessing book record file '{book_file}': {e}")

                self.current_page_num = book_data.get("last_page", self.current_page_num)
                self.current_sentence_idx = book_data.get("last_sentence_idx", 0)
                self.save_session()

                return {
                    "book_id": matched_book_id,
                    "is_new_book": False,
                    "last_page": self.current_page_num,
                    "last_sentence_idx": self.current_sentence_idx,
                    "book_data": book_data
                }

            # 4. Create New Book Record
            new_book_id = f"book_{hashlib.md5(text[:50].encode('utf-8')).hexdigest()[:8]}"
            sample_words = list(set([w.lower() for w in text.split()[:20] if len(w) > 3]))

            book_data = {
                "book_id": new_book_id,
                "detected_lang": detected_lang,
                "created_at": time.time(),
                "last_page": 1,
                "last_sentence_idx": 0,
                "fingerprints": [fingerprint] if fingerprint else [],
                "sample_words": sample_words,
                "pages_read": 1
            }

            book_file = os.path.join(self.books_dir, f"{new_book_id}.json")
            try:
                with open(book_file, "w", encoding="utf-8") as f:
                    json.dump(book_data, f, indent=2)
                logger.info(f"Created new book record: '{new_book_id}'")
            except Exception as e:
                logger.warning(f"Could not persist new book record '{book_file}': {e}")

            self.current_book_id = new_book_id
            self.current_page_num = 1
            self.current_sentence_idx = 0
            self.save_session()

            return {
                "book_id": new_book_id,
                "is_new_book": True,
                "last_page": 1,
                "last_sentence_idx": 0,
                "book_data": book_data
            }

        except Exception as ex:
            logger.warning(f"Book memory identification exception ({ex}). Gracefully continuing without memory persistence.")
            return {
                "book_id": self.current_book_id,
                "is_new_book": False,
                "last_page": self.current_page_num,
                "last_sentence_idx": 0,
                "book_data": {}
            }

    def _get_existing_book_result(self, book_id, is_new):
        book_data = {}
        try:
            book_file = os.path.join(self.books_dir, f"{book_id}.json")
            if os.path.exists(book_file):
                with open(book_file, "r", encoding="utf-8") as f:
                    book_data = json.load(f)
        except Exception as e:
            logger.warning(f"Error loading book record for '{book_id}': {e}")

        return {
            "book_id": book_id,
            "is_new_book": is_new,
            "last_page": self.current_page_num,
            "last_sentence_idx": self.current_sentence_idx,
            "book_data": book_data
        }

    def update_progress(self, page_num, sentence_idx):
        """Updates reading progress for active book safely without raising exceptions."""
        try:
            self.current_page_num = max(1, page_num)
            self.current_sentence_idx = max(0, sentence_idx)
            self.last_processed_page = max(self.last_processed_page, self.current_page_num)
            self.save_session()

            if self.current_book_id:
                book_file = os.path.join(self.books_dir, f"{self.current_book_id}.json")
                if os.path.exists(book_file):
                    with open(book_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["last_page"] = max(data.get("last_page", 1), self.current_page_num)
                    data["last_sentence_idx"] = self.current_sentence_idx
                    data["pages_read"] = max(data.get("pages_read", 1), self.current_page_num)
                    with open(book_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to update book progress file ({e}). Degrading gracefully.")

    def reset_book_progress(self, book_id):
        """Resets a book's reading position back to beginning (Page 1, Sentence 0)."""
        self.current_page_num = 1
        self.current_sentence_idx = 0
        self.update_progress(1, 0)
        logger.info(f"Reset reading progress for book '{book_id}' back to page 1.")

    def _list_all_books(self):
        """Reads all stored book JSON records safely."""
        books = {}
        if not os.path.exists(self.books_dir):
            return books

        try:
            for filename in os.listdir(self.books_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(self.books_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            b_id = data.get("book_id", filename.replace(".json", ""))
                            books[b_id] = data
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Could not list books directory ({e}). Returning empty cache.")

        return books
