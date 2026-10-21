# Calcelyx 1.0

Lokalna aplikacja Windows do przygotowywania wycen prac remontowo-wykończeniowych. Działa bez internetu i nie wymaga programu Excel.

## Najważniejsze funkcje

- obsługa klientów, inwestycji i pomieszczeń;
- ręczne dodawanie i edycja pomieszczeń wraz z wymiarami drzwi i okien;
- obliczanie podłóg, sufitów, ścian i listew;
- odrysowanie wielokątnego obrysu na podkładzie PDF, JPG lub PNG;
- kalibracja skali, powiększanie, przesuwanie oraz cofanie zmian;
- cennik edytowany w aplikacji lub Excelu z walidacją importu;
- odpady, mnożnik trudności, minimalne stawki, narzut, rabat i VAT;
- ręcznie wprowadzane kilometry, wizyty, parking i koszt dojazdu;
- oferta PDF, szczegółowy kosztorys Excel, lokalna baza, rewizje i kopie zapasowe;
- angielski i polski interfejs wybierany w `Ustawieniach`.
- walutę ustawianą osobno dla każdego projektu w `Ustawieniach` (PLN, EUR, USD, GBP, CHF, CZK, SEK, NOK lub DKK).

## Język

Domyślnym językiem aplikacji jest angielski. W widoku `Ustawienia` wybierz `Polski`, aby przełączyć interfejs i eksportowane dokumenty. Własne nazwy pomieszczeń, dane klientów i opisy usług nie są automatycznie tłumaczone.

Walutę wyceny wybiera się osobno w `Ustawienia` → `Reguły oferty`. Zmiana obejmuje kwoty w aplikacji oraz nowe eksporty PDF i Excel. Starsze projekty bez zapisanej waluty używają PLN.

## Uruchomienie gotowej aplikacji

1. Pobierz `Calcelyx-1.0-Windows.zip` z najnowszego wydania GitHub.
2. Rozpakuj całe archiwum do folderu, w którym masz prawo zapisu.
3. Uruchom `Calcelyx.exe` i pozostaw go razem z folderem `_internal`.

Po samodzielnym zbudowaniu projektu taki sam folder aplikacji znajduje się w `dist/Calcelyx`.

## Edytowalne cenniki

- `data/Calcelyx_Price_List_EN.xlsx` — wersja angielska;
- `data/Calcelyx_Cennik_PL.xlsx` — wersja polska.

Kwoty są wyłącznie przykładowe i nie są zweryfikowanymi cenami rynkowymi. Przed przygotowaniem oferty zastąp je stawkami firmy. Zachowaj kody pozycji i wymagane nazwy kolumn.

## Odrysowanie rzutu PDF

1. Wejdź w `Rzut i obmiary`.
2. Wybierz `Otwórz PDF / obraz`.
3. Dopasuj stronę, skalibruj rzut na znanym wymiarze i narysuj obrys główny.
4. Dla każdego pokoju utwórz osobny obrys i zapisz go jako pomieszczenie.
5. `Ctrl+rolka` zmienia powiększenie, środkowy przycisk przesuwa, a `Ctrl+Z` i `Ctrl+Y` cofają i ponawiają zmiany.

Program nie interpretuje automatycznie ścian ani wymiarów z dokumentacji.

## Ważne informacje

- aplikacja nie rozstrzyga prawidłowej stawki VAT;
- wykonawca powinien sprawdzić wszystkie wymiary, ceny i zakres robót;
- przed dużą zmianą cennika warto utworzyć kopię zapasową;
- ofertę wysłaną lub zaakceptowaną należy zapisać jako osobną rewizję.

## Uruchomienie kodu źródłowego

```text
python -m pip install -r requirements.txt
run_dev.cmd
```

Testy:

```text
set PYTHONPATH=src
python -m pytest -q
```

Calcelyx jest udostępniany na licencji MIT. Komponenty zewnętrzne i ich licencje opisuje plik `THIRD-PARTY-NOTICES.txt`.

