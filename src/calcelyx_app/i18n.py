"""Small runtime localization layer for the desktop interface.

The original interface was written in Polish.  English is the public default,
while Polish remains available without maintaining a second GUI codebase.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


SUPPORTED_LANGUAGES = {"en": "English", "pl": "Polski"}
_language = "en"
_installed = False


EN: dict[str, str] = {
    "wersja 1.0 • offline": "version 1.0 • offline",
    "Pulpit": "Dashboard", "Inwestycja": "Project", "Rzut i obmiary": "Plan & measurements",
    "Kosztorys": "Estimate", "Cennik": "Price list", "Cennik robót": "Price list", "Ustawienia": "Settings", "Waluta": "Currency",
    "Zapisz": "Save", "Eksport PDF": "Export PDF", "Dane przechowywane lokalnie": "Data stored locally",
    "Niezapisane zmiany": "Unsaved changes", "Zapisano lokalnie • ": "Saved locally • ",
    "Projekt został zapisany.": "Project saved.", "Nowy projekt": "New project", "Otwórz projekt": "Open project",
    "Kontynuuj wycenę": "Continue estimate", "Dobra wycena zaczyna się od dobrego obmiaru.": "A reliable estimate starts with accurate measurements.",
    "Rzut, cennik, kosztorys i gotowa oferta — lokalnie, bez chmury.": "Plans, measurements, pricing and a ready quote — stored locally, without the cloud.",
    "Pomieszczenia": "Rooms", "Powierzchnia": "Area", "Pozycje": "Items", "Wartość brutto": "Gross value",
    "w bieżącym projekcie": "in the current project", "łączna podłoga": "total floor area", "w kosztorysie": "in the estimate", "bieżąca wersja": "current version",
    "Bieżąca wycena": "Current estimate", "Gotowość oferty": "Quote readiness", "Nie podano": "Not provided",
    "Nazwa": "Name", "Numer": "Number", "Klient": "Client", "Adres": "Address", "Edytuj dane inwestycji": "Edit project details",
    "Dane klienta": "Client details", "Pomieszczenia i obmiary": "Rooms and measurements", "Pozycje kosztorysu": "Estimate items", "Dane wykonawcy": "Contractor details",
    "Dane projektu i klienta": "Project and client details", "Nazwa projektu": "Project name", "Numer oferty": "Quote number", "Data": "Date",
    "Telefon": "Phone", "E-mail": "Email", "Adres inwestycji": "Project address",
    "＋ Dodaj pomieszczenie ręcznie": "＋ Add room manually", "Otwórz rzut — skaluj, przesuń i wykonaj obmiar": "Open plan — scale, pan and measure",
    "Edytuj zaznaczone": "Edit selected",
    "Kliknij dwukrotnie wiersz, aby edytować wymiary, drzwi i okna.": "Double-click a row to edit dimensions, doors and windows.",
    "Pomieszczenie": "Room", "Podłoga": "Floor", "Ściany netto": "Net walls", "Sufit": "Ceiling", "Listwy": "Baseboards",
    "Okna: dł. / pole": "Windows: width / area", "Wysokość": "Height", "Przywróć ostatnio usunięte": "Restore last deleted",
    "Usuń zaznaczone": "Delete selected", "Nowe pomieszczenie": "New room", "Edytuj pomieszczenie": "Edit room",
    "Dla prostokąta podaj długość i szerokość. Dla obrysu z rzutu możesz skorygować bezpośrednio pole i obwód.": "For a rectangular room, enter length and width. For a traced outline, you can adjust area and perimeter directly.",
    "Nazwa pomieszczenia": "Room name", "Długość pomieszczenia [m] — opcjonalnie": "Room length [m] — optional",
    "Szerokość pomieszczenia [m] — opcjonalnie": "Room width [m] — optional", "Wysokość [m]": "Height [m]",
    "Powierzchnia podłogi/sufitu [m²]": "Floor/ceiling area [m²]", "Obwód ścian [m]": "Wall perimeter [m]",
    "Łączna szerokość drzwi [m]": "Total door width [m]", "Łączna powierzchnia drzwi [m²]": "Total door area [m²]",
    "Łączna długość/szerokość okien [m]": "Total window width [m]", "Łączna powierzchnia okien [m²]": "Total window area [m²]",
    "Zapisz pomieszczenie": "Save room", "Anuluj": "Cancel", "Podaj nazwę pomieszczenia.": "Enter a room name.",
    "Podaj jednocześnie długość i szerokość albo pozostaw oba pola puste.": "Enter both length and width, or leave both fields blank.",
    "Łączna powierzchnia drzwi i okien musi być mniejsza od powierzchni ścian brutto.": "The total door and window area must be smaller than the gross wall area.",
    "Powierzchnia drzwi i okien nie może być większa niż powierzchnia ścian brutto.": "Door and window area cannot exceed the gross wall area.",
    "Narzędzia": "Tools", "Otwórz PDF / obraz": "Open PDF / image", "Obrys główny": "Main outline", "＋ Główny": "＋ Main",
    "＋ Pokój": "＋ Room", "Usuń aktywny obrys": "Delete active outline", "✎ Rysuj": "✎ Draw", "✥ Przesuń": "✥ Pan",
    "Dopasuj stronę": "Fit page", "Kalibruj skalę": "Calibrate scale", "Zamknij obrys": "Close outline",
    "↶ Cofnij": "↶ Undo", "↷ Ponów": "↷ Redo", "Wyczyść obrys": "Clear outline", "Przezroczystość podkładu": "Background opacity",
    "Zapisz jako pomieszczenie": "Save as room", "Brak obrysów": "No outlines", "Obrys główny lokalu": "Property main outline",
    "AKTYWNY OBRYS": "ACTIVE OUTLINE", "Główny — ": "Main — ", "Pokój ": "Room ",
    "Pole: ": "Area: ", "Pole podglądowe: ": "Preview area: ", "Obwód: ": "Perimeter: ", "Otwarty obrys: ": "Open outline: ",
    "Kliknij punkt 1, aby zamknąć": "Click point 1 to close", "Najpierw zamknij obrys pomieszczenia.": "Close the room outline first.",
    "Obrys główny opisuje cały lokal. Utwórz osobny obrys pokoju przyciskiem „+ Pokój”.": "The main outline represents the whole property. Create a separate room outline with the ‘+ Room’ button.",
    "Obrys przecina sam siebie albo ma zerowe pole. Popraw punkty przed zapisaniem pomieszczenia.": "The outline intersects itself or has zero area. Correct its points before saving the room.",
    "Rozkład pomieszczeń projektu": "Project room summary", "Brak pomieszczeń. Dodaj je w widoku Inwestycja lub Rzut i obmiary.": "No rooms yet. Add them in Project or Plan & measurements.",
    "＋ Dodaj z cennika": "＋ Add from price list", "Edytuj zaznaczoną": "Edit selected", "Przypisz pomieszczenie": "Assign room",
    "Dodaj dojazd": "Add travel", "Eksport Excel": "Export Excel", "Utwórz rewizję": "Create revision", "Historia rewizji": "Revision history",
    "Praca / materiał": "Work / material", "Ilość": "Quantity", "Jednostka": "Unit", "Robocizna": "Labor", "Materiał": "Material",
    "Netto": "Net", "Brutto": "Gross", "Przypisz": "Assign", "zaznaczone pozycje": "selected items",
    "Wartość": "Value", "Zakres": "Scope", "W cenie": "Included", "Opcja": "Option", "Bez przypisania": "Unassigned",
    "Przywróć usunięte": "Restore deleted", "Netto  ": "Net  ", "Brutto  ": "Gross  ",
    "Dodaj pozycję": "Add item", "Dodaj pozycję z cennika": "Add item from price list", "Szukaj po nazwie, kodzie lub kategorii…": "Search by name, code or category…",
    "Kod": "Code", "Kategoria": "Category", "J.m.": "Unit", "Własna ilość": "Custom quantity", "Ściany": "Walls",
    "Odpad %": "Waste %", "Trudność": "Difficulty", "Dodaj do kosztorysu": "Add to estimate",
    "Wybierz pozycję z tabeli.": "Select an item from the table.", "Cennik jest pusty. Najpierw zaimportuj lub utwórz cennik.": "The price list is empty. Import or create a price list first.",
    "Przypisz ": "Assign ", "Wybierz pomieszczenie albo usuń przypisanie.": "Select a room or remove the assignment.", "Zapisz przypisanie": "Save assignment",
    "Edytuj pozycję kosztorysu": "Edit estimate item", "Robocizna netto / jednostkę": "Net labor / unit", "Materiał netto / jednostkę": "Net material / unit",
    "Odpad": "Waste", "Odpad [%]": "Waste [%]", "Mnożnik trudności": "Difficulty multiplier", "VAT [%]": "VAT [%]", "Uwzględnij w sumie oferty": "Include in quote total",
    "Zapisz zmiany": "Save changes", "Dojazd — dane ręczne": "Travel — manual entry",
    "Moduł działa całkowicie offline. Podaj rzeczywisty dystans i liczbę wizyt.": "This module works fully offline. Enter the actual distance and number of visits.",
    "Dystans w jedną stronę [km]": "One-way distance [km]", "Liczba wizyt [całkowita]": "Number of visits [whole number]",
    "Stawka netto za 1 km": "Net rate per km", "Bezpłatny dystans na jedną trasę [km]": "Free distance per trip [km]",
    "Parking i opłaty dla całego projektu": "Parking and fees for the whole project", "Licz trasę w obie strony": "Count round trip",
    "Dodaj koszt do kosztorysu": "Add travel cost to estimate", "Zapisz koszt dojazdu": "Save travel cost", "Dojazdy, parking i opłaty": "Travel, parking and fees",
    "Długość": "Length", "Szerokość": "Width", "Długość okien": "Window width", "Szerokość drzwi": "Door width",
    "Łączna szerokość drzwi": "Total door width", "Powierzchnia podłogi": "Floor area", "Obwód ścian": "Wall perimeter",
    "Bezpłatny dystans": "Free distance", "Parking i opłaty": "Parking and fees", "Minimalna wartość": "Minimum charge",
    "＋ Dodaj usługę": "＋ Add service", "Importuj Excel": "Import Excel", "Eksportuj do Excela": "Export to Excel",
    "Przywróć usuniętą": "Restore deleted", "Usuń zaznaczoną": "Delete selected", "Edytuj usługę": "Edit service",
    "Dodaj usługę": "Add service", "Edytuj usługę i ceny": "Edit service and prices", "Nowa usługa w cenniku": "New price-list service",
    "Kwoty podawaj netto. Przecinek i kropka są akceptowane.": "Enter net amounts. Both comma and decimal point are accepted.",
    "Kod (A-Z, 0-9, _ lub -)": "Code (A-Z, 0-9, _ or -)", "Nazwa usługi": "Service name", "Jednostka (np. m², mb, szt.)": "Unit (e.g. m², lm, pcs)",
    "Robocizna netto": "Net labor", "Materiał netto": "Net material", "Domyślny odpad [%]": "Default waste [%]", "Minimalna wartość netto": "Minimum net charge", "Notatki": "Notes",
    "Usługa aktywna i widoczna przy dodawaniu do kosztorysu": "Service active and available when adding estimate items", "Zapisz usługę": "Save service",
    "Dane wykonawcy": "Contractor details", "Nazwa firmy": "Company name", "Dane kontaktowe / NIP": "Contact details / tax ID",
    "Reguły oferty": "Quote rules", "Narzut od kosztu [%]": "Markup on cost [%]", "Rabat po naliczeniu narzutu [%]": "Discount after markup [%]",
    "Ważność oferty [dni]": "Quote validity [days]", "Domyślne założenia i wyłączenia": "Default assumptions and exclusions",
    "Zapisz ustawienia": "Save settings", "Kopie zapasowe": "Backups",
    "Baza oraz bieżący projekt są zapisywane lokalnie. Utwórz dodatkową kopię przed większą zmianą cennika.": "The database and current project are stored locally. Create an extra backup before making major price-list changes.",
    "Utwórz kopię teraz": "Create backup now", "Przywróć kopię…": "Restore backup…",
    "Język aplikacji": "Application language", "Wybierz język interfejsu i dokumentów eksportowanych.": "Choose the language used by the interface and exported documents.",
    "Odzyskiwanie danych": "Data recovery", "Nieprawidłowa wartość": "Invalid value", "Nieprawidłowe dane": "Invalid data",
    "Nieprawidłowe dane pomieszczenia": "Invalid room data", "Nieprawidłowe otwory": "Invalid openings", "Nieprawidłowy obrys": "Invalid outline",
    "Nieprawidłowa wysokość": "Invalid height", "Nieprawidłowe dane pozycji": "Invalid item data", "Nieprawidłowe dane dojazdu": "Invalid travel data",
    "Nieprawidłowy kod": "Invalid code", "Duplikat kodu": "Duplicate code", "Brak wymaganych danych": "Missing required data", "Nieprawidłowa jednostka": "Invalid unit",
    "Błędy w cenniku": "Price-list errors", "Import cennika": "Import price list", "Usuń usługę": "Delete service", "Usuń pozycje": "Delete items",
    "Usuń pomieszczenie": "Delete room", "Usuń obrys": "Delete outline", "Podkład": "Background", "Kalibracja": "Calibration", "Kalibracja skali": "Scale calibration",
    "Przywracanie kopii": "Restore backup", "Oferta nie jest kompletna": "Quote is incomplete", "Podgląd oferty": "Quote preview",
    "Eksport zakończony": "Export complete", "Otwieranie projektu": "Open project", "Nie można utworzyć rewizji": "Cannot create revision",
    "Historia rewizji": "Revision history", "Cennik Excel został zapisany.": "Price-list workbook saved.", "Zaimportowano nową wersję cennika.": "Imported a new price-list version.",
    "Kosztorys Excel jest gotowy.": "Estimate workbook is ready.", "Oferta PDF jest gotowa.": "Quote PDF is ready.",
    "Eksportuj ofertę PDF": "Export quote PDF", "Przywróć kopię": "Restore backup", "Wybrano obrys główny.": "Selected the main outline.",
    "Kod musi mieć 2–40 znaków i może zawierać tylko A-Z, 0-9, _ oraz -.": "The code must contain 2–40 characters and may use only A-Z, 0-9, _ and -.",
    "Uzupełnij kategorię, nazwę i jednostkę.": "Complete the category, name and unit.", "” już istnieje w cenniku.": "’ already exists in the price list.",
    "Nazwa obrysu nie może być pusta": "Outline name cannot be empty", "Nieobsługiwany tryb: ": "Unsupported mode: ",
    "Nieprawidłowy numer strony PDF": "Invalid PDF page number", "kind musi mieć wartość 'main' albo 'room'": "kind must be 'main' or 'room'",
    "Plik jest większy niż 100 MB. Zmniejsz PDF przed wczytaniem.": "The file is larger than 100 MB. Reduce the PDF size before opening it.",
    "Nie udało się odczytać ostatniego projektu:\n": "Could not read the last project:\n", "Nie udało się odczytać pliku:\n": "Could not read the file:\n",
    "Nie udało się otworzyć pliku:\n": "Could not open the file:\n", "Nie udało się otworzyć projektu:\n": "Could not open the project:\n",
    "Nie udało się utworzyć oferty:\n": "Could not create the quote:\n", "Nie udało się utworzyć pliku:\n": "Could not create the file:\n",
    "Najpierw zaznacz pomieszczenie.": "Select a room first.", "Najpierw zaznacz pozycję do usunięcia.": "Select an item to delete first.",
    "Najpierw zaznacz jedną lub kilka pozycji.": "Select one or more items first.", "Najpierw zaznacz pozycję.": "Select an item first.",
    "Najpierw zaznacz usługę w tabeli.": "Select a service in the table first.", "Nie utworzono jeszcze żadnej rewizji.": "No revisions have been created yet.",
    "Wybierz rzut": "Select plan", "PDF lub obraz": "PDF or image", "Obrazy": "Images", "Strona PDF": "PDF page",
    "Dokument ma ": "The document has ", " stron. Podaj numer strony do odrysowania:": " pages. Enter the page number to trace:",
    "Wysokość w metrach:": "Height in meters:", "Nazwa pomieszczenia, np. Salon:": "Room name, e.g. Living room:",
    "Nazwa pomieszczenia:": "Room name:", "Nowy obrys pomieszczenia": "New room outline", "Znany wymiar": "Known dimension",
    "Rzeczywista odległość [m]:": "Actual distance [m]:", "Najpierw otwórz PDF lub obraz rzutu.": "Open a PDF or plan image first.",
    "Kliknij kolejno dwa końce znanego wymiaru na rzucie.": "Click the two endpoints of a known dimension on the plan.",
    "Wyczyść obrys": "Clear outline", "Usunąć cały obrys? Możesz go przywrócić skrótem Ctrl+Z.": "Delete the entire outline? You can restore it with Ctrl+Z.",
    "Zapisać bieżący projekt i rozpocząć nowy?": "Save the current project and start a new one?", "Projekt Calcelyx": "Calcelyx project",
    "Wybierz folder kopii": "Select backup folder", "Wybrany folder nie zawiera kompletnej kopii Calcelyx.": "The selected folder does not contain a complete Calcelyx backup.",
    "Bieżące dane zostaną najpierw zapisane, a następnie zastąpione zawartością kopii. Kontynuować?": "Current data will be saved first and then replaced with the backup. Continue?",
    "Kopia została przywrócona.": "Backup restored.", "Oferta została zapisana. Otworzyć ją teraz?": "The quote was saved. Open it now?",
    "Uzupełnij dane przed eksportem:\n\n• ": "Complete the following before export:\n\n• ", "Uzupełnij:\n\n• ": "Complete:\n\n• ",
    "nazwa inwestycji — ekran Inwestycja": "project name — Project screen", "numer oferty — ekran Inwestycja": "quote number — Project screen",
    "data oferty — ekran Inwestycja": "quote date — Project screen", "nazwa klienta — ekran Inwestycja": "client name — Project screen",
    "adres inwestycji — ekran Inwestycja": "project address — Project screen", "co najmniej jedna pozycja uwzględniona w kosztorysie": "at least one included estimate item",
    "narzut": "markup", "rabat": "discount", "ważność oferty": "quote validity", "dni": "days", "Waluta wyceny": "Estimate currency",
    "Pole „": "Field ‘", "” jest wymagane.": "’ is required.", "” musi zawierać liczbę, np. 12,50.": "’ must contain a number, e.g. 12.50.",
    "” musi zawierać skończoną liczbę.": "’ must contain a finite number.", "” musi zawierać liczbę całkowitą.": "’ must contain a whole number.",
    "” nie może być mniejsze niż ": "’ cannot be less than ", "” nie może być większe niż ": "’ cannot be greater than ",
    "Nowa wycena": "New estimate", "Twoja Firma Wykończeniowa": "Your Finishing Company", "Uzupełnij dane firmy w Ustawieniach": "Complete company details in Settings",
    "OF/": "QT/", "Oferta": "Quote", "TWOJA FIRMA": "YOUR COMPANY", "Dane firmy do uzupełnienia": "Complete company details",
    "OFERTA WYCENY": "PROJECT QUOTE", "Nr": "No.", "KLIENT": "CLIENT", "INWESTYCJA": "PROJECT", "WAŻNOŚĆ": "VALIDITY",
    "Zakres i wycena": "Scope and pricing", "Lp.": "No.", "Pomieszczenie / praca": "Room / work", "Cena netto": "Net unit price",
    "Wartość netto": "Net value", "Suma pozycji": "Items subtotal", "Narzut": "Markup", "Rabat": "Discount", "Razem netto": "Net total",
    "RAZEM BRUTTO": "GROSS TOTAL", "Założenia i uwagi": "Assumptions and notes", "Opcje nieuwzględnione w sumie": "Options excluded from total",
    "netto": "net", "Wykonawca": "Contractor", "Akceptacja klienta": "Client approval", "wygenerowano w": "generated with", "Strona": "Page",
    "Robocizna netto/j.m.": "Net labor/unit", "Materiał netto/j.m.": "Net material/unit", "Cena łączna netto/j.m.": "Total net price/unit",
    "Wliczona": "Included", "Wzór / uwagi": "Formula / notes", "TAK": "YES", "NIE": "NO",
    "Wycena została przygotowana na podstawie podanych wymiarów. Prace ukryte i niemożliwe do oceny przed rozpoczęciem robót wymagają osobnego uzgodnienia.": "This estimate is based on the provided measurements. Concealed work and conditions that cannot be assessed before work begins require separate agreement.",
    "Nieprawidłowy cennik:\n": "Invalid price list:\n", "wiersz ": "row ", "arkusz": "sheet", ", pole ": ", field ",
    "wartość jest wymagana": "value is required", "użyj 2–40 znaków: A-Z, 0-9, _ lub -": "use 2–40 characters: A-Z, 0-9, _ or -",
    "niedozwolona jednostka ": "unsupported unit ", "oczekiwano liczby": "expected a number", "wartość nie może być ujemna": "value cannot be negative",
    "wartość musi być w zakresie 0–100": "value must be between 0 and 100", "użyj TAK/NIE, TRUE/FALSE albo 1/0": "use YES/NO, TRUE/FALSE or 1/0",
    "brak wymaganego arkusza": "required sheet is missing", "arkusz jest pusty": "sheet is empty", "brak wymaganej kolumny": "required column is missing",
    "duplikat kodu ": "duplicate code ", "pierwszy raz w wierszu ": "first occurrence in row ", "duplikat ustawienia ": "duplicate setting ",
    "1. Otwórz i skalibruj rzut\n2. Narysuj obrys główny\n3. Twórz osobne obrysy pomieszczeń\n4. Kliknij punkt 1, aby zamknąć dokładnie\n\nCtrl+rolka: zoom • środkowy: przesuń\nCtrl+Z / Ctrl+Y: cofnij / ponów": "1. Open and calibrate the plan\n2. Draw the main outline\n3. Create separate room outlines\n4. Click point 1 to close precisely\n\nCtrl+wheel: zoom • middle button: pan\nCtrl+Z / Ctrl+Y: undo / redo",
    " pozycji • kliknij dwukrotnie, aby edytować cenę": " items • double-click to edit a price",
    "robocizna: ": "labor: ", "; materiał: ": "; material: ", "% odpadu materiałowego": "% material waste", " × trudność ": " × difficulty ",
    "% odpadu; trudność × ": "% waste; difficulty × ", " + opłaty ": " + fees ", "W cenie": "Included", "Opcja": "Option",
    "Klient: ": "Client: ", "Adres: ": "Address: ", "Pozycji w cenie: ": "Included items: ", "Netto: ": "Net: ", "Brutto: ": "Gross: ",
    "Ważność: ": "Validity: ", " dni\n\nUtworzyć ofertę PDF?": " days\n\nCreate the quote PDF?",
    "Poprawnie odczytano ": "Successfully read ", " pozycji.\n\nZastąpić obecny cennik?": " items.\n\nReplace the current price list?",
    "Przywrócono pomieszczenia: ": "Restored rooms: ", "Utworzono kopię: ": "Created backup: ", "Utworzono rewizję ": "Created estimate revision ",
    "Przypisano pozycje: ": "Assigned items: ", "Zapisano pomieszczenie „": "Saved room ‘", "Utworzono obrys pomieszczenia „": "Created room outline ‘",
    "Usunąć ": "Delete ", " zaznaczone pomieszczenie(a)?": " selected room(s)?", " zaznaczone pozycje kosztorysu?": " selected estimate items?",
    "Powiązane pozycje kosztorysu: ": "Related estimate items: ", ". Pozostaną w kosztorysie jako „Bez przypisania”.": ". They will remain in the estimate as ‘Unassigned’.",
    " Powiązane pomieszczenie i jego pomiary również zostaną usunięte.": " The linked room and its measurements will also be deleted.",
    " kosztorysu.": " of the estimate.", " pozycji.": " items.", " z cennika? Istniejące pozycje kosztorysu pozostaną bez zmian.": " from the price list? Existing estimate items will remain unchanged.",
}

FRAGMENT_KEYS = (
    "Zapisano lokalnie • ", "Nie udało się odczytać ostatniego projektu:\n", "Nie udało się odczytać pliku:\n",
    "Nie udało się otworzyć pliku:\n", "Nie udało się otworzyć projektu:\n", "Nie udało się utworzyć oferty:\n", "Nie udało się utworzyć pliku:\n",
    "Pole „", "” jest wymagane.", "” musi zawierać liczbę, np. 12,50.", "” musi zawierać skończoną liczbę.",
    "” musi zawierać liczbę całkowitą.", "” nie może być mniejsze niż ", "” nie może być większe niż ",
    "Główny — ", "Pokój ", "Pole: ", "Pole podglądowe: ", "Obwód: ", "Otwarty obrys: ", "Kliknij punkt 1, aby zamknąć",
    " pozycji • kliknij dwukrotnie, aby edytować cenę", "robocizna: ", "; materiał: ", "% odpadu materiałowego", " × trudność ",
    "% odpadu; trudność × ", " + opłaty ", "Klient: ", "Adres: ", "Pozycji w cenie: ", "Netto: ", "Brutto: ", "Ważność: ",
    " dni\n\nUtworzyć ofertę PDF?", "Poprawnie odczytano ", " pozycji.\n\nZastąpić obecny cennik?", "Przywrócono pomieszczenia: ",
    "Utworzono kopię: ", "Utworzono rewizję ", "Przypisano pozycje: ", "Zapisano pomieszczenie „", "Utworzono obrys pomieszczenia „",
    "Usunąć ", " zaznaczone pomieszczenie(a)?", " zaznaczone pozycje kosztorysu?", "Powiązane pozycje kosztorysu: ",
    ". Pozostaną w kosztorysie jako „Bez przypisania”.", " Powiązane pomieszczenie i jego pomiary również zostaną usunięte.",
    " kosztorysu.", " pozycji.", " z cennika? Istniejące pozycje kosztorysu pozostaną bez zmian.",
    "Nieobsługiwany tryb: ", "wiersz ", ", pole ", "niedozwolona jednostka ", "duplikat kodu ", "pierwszy raz w wierszu ", "duplikat ustawienia ",
)


def set_language(language: str) -> str:
    global _language
    _language = language if language in SUPPORTED_LANGUAGES else "en"
    return _language


def get_language() -> str:
    return _language


def tr(value: Any, language: str | None = None) -> Any:
    """Translate a UI string, including known fragments in dynamic messages."""
    if not isinstance(value, str) or (language or _language) == "pl":
        return value
    if value in EN:
        return EN[value]
    translated = value
    for source in sorted(FRAGMENT_KEYS, key=len, reverse=True):
        if source in translated:
            translated = translated.replace(source, EN[source])
    return translated


def install_ui_localization() -> None:
    """Install transparent translation hooks for Tk/CustomTkinter widgets."""
    global _installed
    if _installed:
        return
    _installed = True

    import customtkinter as ctk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    def patch_widget(name: str, fields: tuple[str, ...] = ("text", "placeholder_text")) -> None:
        original = getattr(ctk, name)

        class Localized(original):  # type: ignore[misc, valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                for field in fields:
                    if field in kwargs:
                        kwargs[field] = tr(kwargs[field])
                super().__init__(*args, **kwargs)

            def configure(self, *args: Any, **kwargs: Any) -> Any:
                for field in fields:
                    if field in kwargs:
                        kwargs[field] = tr(kwargs[field])
                return super().configure(*args, **kwargs)

            config = configure

        Localized.__name__ = original.__name__
        setattr(ctk, name, Localized)

    for widget_name in ("CTkLabel", "CTkButton", "CTkCheckBox", "CTkEntry"):
        patch_widget(widget_name)

    original_combo = ctk.CTkComboBox

    class LocalizedComboBox(original_combo):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._raw_values = list(kwargs.get("values", []))
            self._display_to_raw: dict[str, str] = {}
            kwargs["values"] = self._translated_values(self._raw_values)
            command = kwargs.get("command")
            if command:
                kwargs["command"] = lambda shown: command(self._display_to_raw.get(shown, shown))
            super().__init__(*args, **kwargs)

        def _translated_values(self, values: list[str]) -> list[str]:
            shown = [str(tr(value)) for value in values]
            self._display_to_raw = dict(zip(shown, values))
            return shown

        def configure(self, *args: Any, **kwargs: Any) -> Any:
            if "values" in kwargs:
                self._raw_values = list(kwargs["values"])
                kwargs["values"] = self._translated_values(self._raw_values)
            command = kwargs.get("command")
            if command:
                kwargs["command"] = lambda shown: command(self._display_to_raw.get(shown, shown))
            return super().configure(*args, **kwargs)

        config = configure

        def set(self, value: str) -> None:
            super().set(str(tr(value)))

        def get(self) -> str:
            shown = super().get()
            return self._display_to_raw.get(shown, shown)

    ctk.CTkComboBox = LocalizedComboBox

    original_input_dialog = ctk.CTkInputDialog

    class LocalizedInputDialog(original_input_dialog):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            for field in ("text", "title"):
                if field in kwargs:
                    kwargs[field] = tr(kwargs[field])
            super().__init__(*args, **kwargs)

    ctk.CTkInputDialog = LocalizedInputDialog

    original_title = ctk.CTkToplevel.title

    def localized_title(self: Any, text: str | None = None) -> Any:
        return original_title(self) if text is None else original_title(self, tr(text))

    ctk.CTkToplevel.title = localized_title

    original_heading = ttk.Treeview.heading
    original_insert = ttk.Treeview.insert

    def localized_heading(self: Any, column: Any, option: Any = None, **kwargs: Any) -> Any:
        if "text" in kwargs:
            kwargs["text"] = tr(kwargs["text"])
        return original_heading(self, column, option, **kwargs)

    def localized_insert(self: Any, parent: Any, index: Any, iid: Any = None, **kwargs: Any) -> Any:
        if "values" in kwargs:
            kwargs["values"] = tuple(tr(value) for value in kwargs["values"])
        return original_insert(self, parent, index, iid, **kwargs)

    ttk.Treeview.heading = localized_heading
    ttk.Treeview.insert = localized_insert

    for name in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel"):
        original = getattr(messagebox, name)

        def make_dialog_wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
            def wrapped(title: str, message: str, *args: Any, **kwargs: Any) -> Any:
                return fn(tr(title), tr(message), *args, **kwargs)
            return wrapped

        setattr(messagebox, name, make_dialog_wrapper(original))

    for name in ("askopenfilename", "asksaveasfilename", "askdirectory"):
        original = getattr(filedialog, name)

        def make_file_wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                if "title" in kwargs:
                    kwargs["title"] = tr(kwargs["title"])
                if "filetypes" in kwargs:
                    kwargs["filetypes"] = [(tr(label), pattern) for label, pattern in kwargs["filetypes"]]
                return fn(*args, **kwargs)
            return wrapped

        setattr(filedialog, name, make_file_wrapper(original))

    original_askfloat = simpledialog.askfloat

    def localized_askfloat(title: str, prompt: str, *args: Any, **kwargs: Any) -> Any:
        return original_askfloat(tr(title), tr(prompt), *args, **kwargs)

    simpledialog.askfloat = localized_askfloat
