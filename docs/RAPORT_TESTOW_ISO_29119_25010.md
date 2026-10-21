# Raport końcowy testów — Calcelyx 1.0

Data: 21.10.2026  
Zakres: `dist/Calcelyx/Calcelyx.exe`  
Podejście: testy scenariuszowe inspirowane ISO/IEC/IEEE 29119 oraz ocena cech jakościowych ISO/IEC 25010. Dokument nie stanowi formalnej certyfikacji zgodności.

## Werdykt

**GO — aplikacja nadaje się do pilotażowego użytkowania przez użytkownika końcowego.**

- P0: 0
- P1: 0
- P2: 1 (ograniczenie dostępności czytników ekranu)
- testy automatyczne: 39/39 zaliczone
- test uruchomieniowy GUI: zaliczony
- test uruchomieniowy gotowej binarki Windows: zaliczony

## Zrealizowane scenariusze

| Obszar | Wynik | Dowód / obserwacja |
|---|---:|---|
| Nazwa produktu | PASS | Tytuł okna i interfejs używają `Calcelyx 1.0` |
| Nawigacja | PASS | Pulpit, Inwestycja, Rzut i obmiary, Kosztorys, Cennik, Ustawienia |
| Pomieszczenie ręczne | PASS | Dla 4 × 3 × 2,6 m: podłoga 12,00 m², ściany netto 36,40 m², sufit 12,00 m², listwy 14,00 mb |
| Edycja pomieszczeń | PASS | Edycja wymiarów, obwodu oraz osobnej długości i powierzchni drzwi i okien; automatyczne przeliczenie ścian netto |
| Rysowanie obrysów | PASS | Obrys główny i wiele pokoi, dokładne domknięcie do punktu 1, pole, obwód i walidacja przecięć |
| Cofnij / ponów | PASS | `Ctrl+Z`, `Ctrl+Y` oraz przyciski interfejsu |
| PDF i obrazy | PASS | Import, wybór strony wielostronicowego PDF, dopasowanie widoku |
| Powiększanie i przesuwanie | PASS | `Ctrl+rolka`, środkowy przycisk oraz tryb `Przesuń`; wspólna transformacja podkładu i obrysu |
| Zachowanie widoku | PASS | Zoom i przesunięcie zachowane po zmianie widoku i ponownym uruchomieniu |
| Kalibracja | PASS | Dwa punkty, widoczna linia odniesienia i przeliczenie pomiarów |
| Cennik | PASS | Ręczne dodawanie, edycja, usuwanie/przywracanie oraz import/eksport Excel |
| Kosztorys | PASS | Rozkład powierzchni pomieszczeń nad tabelą, przypisywanie pozycji, usuwanie/przywracanie, robocizna i materiał osobno, VAT, dojazd, rewizje i eksport Excel |
| Projekty | PASS | Czytelne nazwy plików oparte na nazwie inwestycji i kliencie zamiast samego UUID |
| Eksport oferty | PASS | Kontrola kompletności i generowanie czytelnego PDF |
| Waluty | PASS | Waluta projektu jest zapisywana i używana w interfejsie oraz eksportach PDF/Excel; starsze projekty domyślnie używają PLN |
| Kopie zapasowe | PASS | Utworzenie, kopia bezpieczeństwa i ścisłe odtworzenie migawki |
| Walidacja | PASS | Wymagane wartości, zakresy, liczby całkowite, NaN/Infinity, duplikaty kodów i jednostki |

## Retest poprawek użyteczności

Po pierwszej rundzie poprawiono i ponownie sprawdzono:

1. jednoznaczne wyróżnienie aktywnego trybu `Rysuj` / `Przesuń`;
2. opis `Pole podglądowe` dla otwartego konturu i instrukcję jego zamknięcia;
3. pomarańczową linię pomiędzy punktami kalibracji;
4. zachowanie zoomu i przesunięcia po ponownym otwarciu;
5. ścisłe odtwarzanie zawartości kopii po wykonaniu kopii bezpieczeństwa.

Wszystkie powyższe poprawki zaliczyły retest.

## Ocena jakości wg ISO/IEC 25010

| Cecha | Ocena | Uzasadnienie |
|---|---:|---|
| Przydatność funkcjonalna | dobra | Główne przepływy wyceny, obmiaru, cennika i eksportu działają |
| Zdolność do interakcji | dobra | Jasne etykiety, informacje zwrotne, walidacje, potwierdzenia i cofanie |
| Niezawodność | dobra dla pilotażu | Zapis lokalny, kopie, rewizje i testy regresji |
| Bezpieczeństwo użytkowe | dobra | Walidacja danych, podgląd oferty i ostrzeżenie o cenach demonstracyjnych |
| Przenośność | Windows/offline | Dystrybucja typu one-folder, bez wymogu Excela i internetu |
| Utrzymywalność | dobra | Logika domenowa, zapis, raportowanie i UI są rozdzielone; istnieje zestaw testów |

## Pozostałe ograniczenie P2

Kontrolki biblioteki CustomTkinter mają ograniczoną semantykę w systemowym drzewie dostępności. Obsługa wzrokowa i myszą/klawiaturą jest czytelna, lecz pełna współpraca z czytnikami ekranu wymagałaby osobnego etapu technologicznego lub zmiany warstwy UI. Nie blokuje to uzgodnionego pilotażu, ale powinno pozostać w rejestrze dalszych usprawnień.

## Konkluzja

Calcelyx 1.0 spełnia kryterium wydania pilotażowego: brak defektów P0/P1, wszystkie testy automatyczne przechodzą, a niezależny retest głównych ścieżek zakończył się werdyktem GO.
