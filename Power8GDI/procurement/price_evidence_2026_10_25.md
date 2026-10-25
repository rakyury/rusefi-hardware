# Цены ключевых компонентов Sport GDI6 — 25.10.2026

Проверены 15 наименований из фактического BOM; 13 имеют публичные USD-цены. Это **частичная стоимость компонентов**, без платы и монтажа. BUK9230-100B и точный LT3042IMSE#WTRPBF не оценены; нулевые цены им не присваивались.

Источник BOM: `hardware/design/integrated_bom.csv`, 1090 строк; SHA-256 `1b271d76ff05fba18cd44f48c903ff507ad9a806afd3b260bfbaca74929df30d`. Полные ступени, позиции схемы, stock и замечания — [price_evidence_2026_10_25.json](price_evidence_2026_10_25.json).

| BOM MPN | Шт./плату | На 1 плату, USD | На партию 10, USD | Stock в источнике |
|---|---:|---:|---:|---:|
| [BUK9230-100B](https://www.digikey.com/en/products/detail/nexperia-usa-inc/BUK9230-100B-118/1163576) | 24 | нет цены | нет цены | не подтверждён |
| [IPD90N10S4-06](https://www.digikey.com/en/products/detail/infineon-technologies/IPD90N10S406ATMA1/5960269) | 8 | 24.40 | 120.59 | 3409 |
| [TLE9201SG](https://www.digikey.com/en/products/detail/infineon-technologies/TLE9201SGAUMA1/5960696) | 2 | 8.38 | 63.30 | 2817 |
| [INA300AQDGSRQ1](https://www.digikey.com/en/products/detail/texas-instruments/INA300AQDGSRQ1/6181555) | 6 | 11.46 | 76.54 | 113 |
| [LM74800QDRRRQ1](https://www.digikey.com/en/products/detail/texas-instruments/LM74800QDRRRQ1/13627158) | 4 | 12.00 | 82.18 | 0 |
| [TPIC8101DWR](https://www.digikey.com/en/products/detail/texas-instruments/TPIC8101DWR/565628) | 1 | 5.51 | 42.10 | 1943 |
| [LM76003QRNPRQ1](https://www.digikey.com/en/products/detail/texas-instruments/LM76003QRNPRQ1/25880236) | 1 | 6.16 | 47.25 | 0 |
| [TPS62130AQRGTRQ1](https://www.digikey.com/en/products/detail/texas-instruments/TPS62130AQRGTRQ1/4876431) | 1 | 2.94 | 22.00 | 2441 |
| [LT3042IMSE#WTRPBF](https://www.analog.com/en/products/lt3042.html) | 1 | нет цены | нет цены | не подтверждён |
| [LTC6993HS6-1#WTRPBF](https://www.digikey.com/en/products/detail/analog-devices-inc/LTC6993HS6-1-WTRPBF/17039075) | 6 | 47.76 | 342.96 | 404 |
| [STM32F767IIT6](https://www.digikey.com/en/products/detail/stmicroelectronics/STM32F767IIT6/6137850) | 1 | 28.09 | 225.16 | 3034 |
| [MC33PT2001AE](https://www.digikey.com/en/products/detail/nxp-usa-inc/MC33PT2001AE/11590177) | 2 | 32.40 | 256.46 | 71 |
| [TLE9104SHXUMA1](https://www.digikey.com/en/products/detail/infineon-technologies/TLE9104SHXUMA1/8627206) | 6 | 29.04 | 203.38 | 13021 |
| [STGB18N40LZT4](https://www.digikey.com/en/products/detail/stmicroelectronics/STGB18N40LZT4/1880196) | 6 | 15.78 | 101.40 | 1376 |
| [6437288-1](https://www.digikey.com/en/products/detail/te-connectivity-amp-connectors/6437288-1/5428601) | 4 | 68.80 | 571.03 | 560 |

Частичный итог 13 оценённых строк: **$292.72** на одну плату; **$2154.34** на десять (**$215.43/плату**). Это не итог всего BOM.

Цены применены к точным количествам по ступеням каталога: например, INA300 — 6 или 60 шт., а не 1 или 10 шт. Покупка лишних деталей в базовый итог не включена. Для IPD90N10S4-06 отдельно выявлено: 10 шт. за $19.71 дешевле 8 шт. за $24.40; это даёт 2 запасных и экономию $4.69.

## Ограничения и закупочные риски

- BUK9230-100B,118 у DigiKey указан как obsolete. Цены похожих MOSFET и клонов не использованы; замена требует проверки GDI-каскада. [Страница оригинальной детали](https://www.digikey.com/en/products/detail/nexperia-usa-inc/BUK9230-100B-118/1163576).
- LT3042IMSE#WTRPBF — действительный автомобильный вариант, отмеченный ADI как production. Малая партия и наличие не подтверждены; цена неавтомобильного #TRPBF не подставлена. [ADI](https://www.analog.com/en/products/lt3042.html).
- LM74800 и LM76003 на открытых страницах показывали нулевой stock. Цена есть, готовность к немедленной поставке не подтверждена. У LM76003 дата ожидаемого поступления 12-Oct-2026 уже прошла на дату проверки.
- Публичные страницы получены через веб-источник с возрастом от сегодня до двух месяцев. Это не live-корзина и не оферта. Для STGB18N40LZT4 свежий поисковый фрагмент показал более высокую цену, чем открытая страница; обе записи сохранены, baseline использует одну цельную открытую таблицу. Цены и stock нужно перепроверить при закупке.
- Стоимость указана без налогов, пошлин, доставки, упаковочных сборов, технологического запаса, PCB, трафарета, сборки, программирования, теста, корпуса и ответных разъёмов/жгута.
- Имя CLVC1G125QDBVRQ1 сохранено: BOM не исправлялся. RFQ, заказов и резервирования не было.

Проверка данных: все количества и references сверены с BOM, SHA-256 зафиксирован; итоги пересчитаны Decimal по явным ступеням, JSON повторно прочитан.
