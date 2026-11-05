# Собираем спортивный ECU на базе rusEFI

План реализации v1.1 | 25 октября 2026
38 пакетов работ · firmware + собственный клиент · форки + прежний реверс EMU PRO

**Оставляем rusEFI базой и параллельно разрабатываем собственный удобный клиент.** Firmware остаётся нативным C++ с точечными переносами FOME и публичного исторического gurovefi. Наш прежний реверс EMU PRO задаёт доказуемые стадии, единицы и состояния; он не является готовым кодом или полной математикой контроллеров. Главный путь firmware: DI/PI → независимые события → два ТНВД → capacity → режимы и защиты. Клиент начинает работу с симулятора, общей типизированной схемы и полноценного вертикального среза. Первый выпуск включает все обязательные ECU-функции и свой клиент; TC/pit/maps идут после него. Этот документ задаёт будущие изменения и приёмку: новая прошивка, клиент и испытания здесь не выполнены.

| Основа выпуска | Что именно принимаем |
| --- | --- |
| Аппаратура | 6 цилиндров; 6 DI + опционально 6 PI; onboard peak-and-hold; 2 фазированных HPFP; DBW + EWG; впуск/выпуск VVT. |
| Вычисления | MAP/VE и масса; один STFT; свойства топлива/Flex; независимые модели/расписания DI/PI; PI Film; trims топлива/угла и knock retard по цилиндрам. |
| Обязательные функции | ХХ, overrun, boost/turbo/EGT/oil/lambda/pressure защиты; launch/ALS с выходом; sequential cut/FFS; nitrous; native PWM-PID масла/LP; 2 CAN/SENT/LIN. |
| Собственный клиент | Проекты/калибровки, 2D/3D таблицы, live, логи/overlay, диагностика, сервис, update/recovery. Стек/reuse выбирает прототип; Windows предложена первой платформой. |
| Граница профиля | Lua/LTFT исключены. MAF/Alpha-N не альтернативы MAP. Multi-pulse DI, TC, pit и полная Nm-модель не обязательны. Чужой клиент и INI не являются целевой зависимостью. |

### Один договор по данным связывает четыре слоя

**Измерения и validity → физические запросы → арбитр ограничений → события и выходы.** FuelProperties и snapshot сенсоров публикуются согласованно. Режимы запрашивают воздух, угол, наддув и cut, но не пишут выводы напрямую. Fuel allocator возвращает назначенную и неудовлетворённую массу; scheduler подтверждает commit/cancel. Film, STFT и HPFP получают этот результат, а не предполагают, что любая расчётная доза уже впрыснута.

**P0** - контракт, исполнительные пути, защита и первый срез клиента; **P1** - остальные обязательные функции и полный выпуск; **P2** - дополнения. P1 не означает необязательность. Пакет допускает серию малых PR с общей приёмкой. **C/** означает существующий `firmware/controllers/`; «новый» - проектируемый файл/тип. Идентификаторы ECU-01…ECU-38 стабильны.


<!-- page break -->

## Переносим код, а реверс превращаем в контракты

| Источник → задачи | Код / доказательство | Принятое действие и граница |
| --- | --- | --- |
| FS → 06 | SmallPulseAdder [F1](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197) | Точечный lookup для каждой группы; сохранить rusEFI 2D deadtime. Весь injector_model не заменять. |
| F → 05 | Stored Flex [F2](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12) | Live/stored/fallback и preload; добавить age/CRC/refuel и единое использование состава. |
| G + F + R → 07 | STFT maps/error/gates [G1](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/math/closed_loop_fuel_cell.cpp#L69) [F3](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel_cell.cpp#L34) [R11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel.cpp#L102) | Три карты G, relative error F; gates R. Знак remove мигрировать; только один контур. |
| FS/F → 15, 16, 17 | Axes, valid guard, boost-cut table [F4](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/boost_control.cpp#L96) [F5](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L504) [F11](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L223) | Новая FF по конечной цели; сохранить R valid/latch/hysteresis. Не брать getOrZero(MAP). |
| FS/F → 14, 18 | Knock health/debounce; VVT [F6](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/vvt.cpp#L133) [F7](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/sensors/sensor_checker.cpp#L553) [F8](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) | Добавить never-seen/missed-window. VVT переносить поверх R advanced, без двойного FF. |
| F → 04, 22 | Request/limit; ALS path [F9](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13) [F10](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) | Взять структуру запросов. 90 Nm/(g air), ungated/late ALS skip и предел около50% не переносить. |
| G → 08, 38 | Film axes, pedal maps [G2](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/algo/wall_fuel.cpp#L76) [G3](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/actuators/electronic_throttle.cpp#L649) | Tau/beta не равны target-film: только контрольный образец осей/баланса. Selector исправить до update; sensor bypass исключить. |
| EMU → 05, 06, 09-12 | Fuel pipeline/zero-dose/HPFP routing A; формулы B/C [E1](evidence_manifest.md#e1) [E2](evidence_manifest.md#e2) | Определить stage boundaries, no-event и routing tests. Modelled inputs, staging, DI law и полный HPFP controller не восстановлены. |
| EMU → 13, 17, 22 | Ignition/cylinder consumer, caps, ALS exit [E3](evidence_manifest.md#e3) [E4](evidence_manifest.md#e4) [E5](evidence_manifest.md#e5) [E6](evidence_manifest.md#e6) | Задать свои transition/priority/limiter laws. Consumer/branch не доказывают producer или весь контроллер. |
| EMU UI → 08, 14, 19-21 | Film/idle/overrun/knock/pump fields [E7](evidence_manifest.md#e7) [E8](evidence_manifest.md#e8) | Реализовать требуемые настройки с собственной семантикой; metadata не заменяет алгоритм. |
| R/F client → 28-36 | Tuner, binary transport, tables/logs, generator, DFU [U1](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/readme.md#L1) [U2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292) [U3](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java#L189) [U4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288) [U5](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java) [U6](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_console/ui/src/main/java/com/rusefi/maintenance/DfuFlasher.java#L25) | Собственный продукт через fork/reuse либо новый frontend. Runtime INI заменить typed schema; atomic API и UX ещё разработать. |

**Шкала прежнего реверса:** A - непосредственно наблюдаемые адреса, поля, вызовы, ветви; B - согласующаяся реконструкция FPU/семантики, ещё не независимое доказательство; C - закон/helper не восстановлен; UI - поле, единица или ось XML/скриншота. A у metadata означает существование канала. Полные Film/STFT/staging/DI, detection knock, idle и pump PWM laws не доказаны. Все численные примеры ниже - тесты нашей спецификации, не эталонные измеренные выходы EMU. [E0](evidence_manifest.md#e0) [E9](evidence_manifest.md#e9)


<!-- page break -->

## Начинаем с контрактов, затем закрываем выпуск

| Веха | Пакеты и зависимости | Выходной критерий |
| --- | --- | --- |
| M0 · основа | 01→02; 03/04 и28→29→30; simulator/fixtures27 сразу. | Версии/единицы, schema, API, baseline R; клиент читает канал, правит и применяет параметр на симуляторе. |
| M1 · топливо/события | 05→06→09→10→11/12; 08 интегрируется до конечной проверки12. | Раздельные DI/PI, no-event/cancel, mass ledger, 2 HPFP, окончательная capacity проходят host traces. |
| M2 · углы/приводы/защиты | 13→14; 15→16; API17 вводится рано, полная17 после12/14/16. | Нет пути от режима к выводу в обход limits; final angle/cut, EWG и независимые protections проверены. |
| M3 · полный функционал | 07/08,18-26; 20→21,22-24 после защит. Клиент31-36 параллельно, после28-30. | Обязательные сценарии firmware и клиента работают в симуляторе; таблицы/live/logs/service готовы к HIL. |
| M4 · выпуск | 27 и37 после обязательных01-36; стенд/HIL и калиброванное железо. Затем38. | Согласованные firmware+клиент+schema, timing/outputs, fault injection, update recovery и калибровка. |

### Первый транш: восемь конкретных задач

**ECU-01 → ECU-02 → ECU-04**, затем две ветви: **ECU-05 → ECU-06** и **ECU-28 → ECU-29 → ECU-30**. Эти восемь задач дают контракт, основу топлива и клиентский срез «подключение→чтение→редактирование→validation/commit→живой канал». ECU-03, ECU-15 и API ECU-17 ведутся сразу после контрактов. В17 сначала задаются cap/fault/recovery, затем producers: boost и ALS не ждут завершения всех датчиков.

| Можно до выбора железа | Требует точного узла / платы |
| --- | --- |
| Типы, schema, migrations, MAP/fuel math; SPA/STFT/Flex; Film; allocator; state machines; driver mocks; native protocol parsers. | MCU/pinmux/DMA/таймеры; микросхемы peak-and-hold и токовые профили; latency и max RPM; полярность/выходы DBW/EWG. |
| Event simulation, rail topology, HPFP demand; protection timers; свой клиент offline/simulator, schema/API, tables/live/logs и HIL harness. | Двигатель/firing order/cam; injectors/HPFP; общая ли DI-рампа; turbo/knock; число VVT; nitrous wet/dry; CAN/LIN устройства; bootloader recovery. |

Ожидание аппаратных ответов не останавливает нативную математику и симуляцию. Оно блокирует закрытие конкретных электрических и временных критериев ECU-03/10/11/14/15/18/24/25/27. Пороги турбины, токи и калибровки не копируются со скриншотов. Сроки, трудозатраты и проценты готовности здесь не назначаются.


<!-- page break -->

## 01-04 · Контракт, профиль и арбитраж

### ECU-01 · Единицы и контракт доказательств

**P0** · Зависимости: нет · Новая спецификация; EMU A/B/C/UI [E0](evidence_manifest.md#e0) [E1](evidence_manifest.md#e1) [E8](evidence_manifest.md#e8) [E9](evidence_manifest.md#e9)

**Артефакт:** Новый `docs/sport/evidence_contract.md`; `fuel_types.h` в `C/algo/fuel/`.

Задать mg/cyl/cycle, µL, mg/µL, µs, °CA/720°, kPa abs/ΔP и определение EfficiencyLoad. Зафиксировать 261.1/261.2, происхождение фрагментов и неизвестные шкалы. XML min-volume divider=100 µL не доказывает внутреннюю единицу дозы; raw-перенос запрещён контрактом.

**Готово, когда:** 1 mL=1000 µL; 720000 g/m³=0.72 mg/µL; 1 bar=100 kPa. Карта evidence связывает каждую формулу с A/B/C/UI или «наш дизайн». 2D Film помечена нашим требованием; неизвестные шкалы отсутствуют в defaults.

### ECU-02 · Спортивный профиль и схема данных

**P0** · Зависимости: 01 · rusEFI + новая интеграция [R21](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/docs/firmware-flash-usage.md)

**Артефакт:** Существующие `prepend.txt`, исходная schema; новый `docs/sport/donor_manifest.md`.

Закрепить baseline R; создать профиль без Lua/LTFT и альтернатив MAF/Alpha-N. Задать schema version/CRC, единый snapshot входов и номера поколений. Сохранить нужные сервисные инструменты отдельно. Каждому переносу назначить исходный commit/file/line и уведомления об авторстве.

**Готово, когда:** Сборка профиля и схема параметров согласованы; Lua/LTFT отсутствуют в исполняемом профиле, а не только меню. Старые scalar-настройки мигрируют в постоянные карты; неизвестная версия явно отклоняется. Базовая регрессия R зафиксирована.

### ECU-03 · Плата, ресурсы и onboard peak-and-hold

**P0** · Зависимости: 01, 02 · R board + новая аппаратная адаптация [R16](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/hellen/alphax-4K-GDI/board_configuration.cpp)

**Артефакт:** Существующий `firmware/config/boards/hellen/alphax-4K-GDI/`; новые board adapter и `hardware_contract.md`.

Описать 6 DI + опциональные 6 PI, 2 HPFP, DBW/EWG, VVT, 2 knock, CAN/SENT/LIN, Flex/turbo capture. Ввести API driver enable/current-profile/fault/max-hold; закрепить pinmux, timer/DMA/ADC и запрет конфликтующих назначений. Характеристики драйвера задаются после выбора микросхем.

**Готово, когда:** Host mock адресует все каналы; конфликт ресурсов отвергается. На стенде измерены peak/hold, выключение при reset/sync loss и driver fault. Без точной схемы закрывается API, но аппаратная часть пакета остаётся открытой.

### ECU-04 · Общий арбитр запросов и событий cut

**P0** · Зависимости: 01, 02; интеграция 10, 17 · FOME структура + новый арбитр [F9](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13) [F10](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) [R4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L164)

**Артефакт:** Новые `C/modules/sport/request_arbiter.*`, `cut_executor.*`; существующие LimpManager/spark consumers.

ModeRequest хранит владельца, срок, reason и отдельные air/boost/angle/fuel/cut поля. Авария выше режимов. Не переносить 90 Nm/(g air) как модель момента. Решение о пропуске использует текущую долю до события; fuel cut согласован между DI/PI и N2O.

**Готово, когда:** 0% = нет пропусков, 100% = полный cut; промежуточные доли сбалансированы по цилиндрам. Disabled ALS при сохранённом ratio не влияет; stale запрос истекает. ALS+shift+oil fault даёт один воспроизводимый разрешённый выход и полную маску причин.


<!-- page break -->

## 05-08 · Масса топлива и переходные коррекции

### ECU-05 · MAP-модель и единые свойства топлива

**P0** · Зависимости: 01, 02 · R model + FOME Flex; EMU pipeline [R10](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/fuel_computer.cpp#L22) [F2](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12) [E1](evidence_manifest.md#e1)

**Артефакт:** Существующий `C/algo/fuel/fuel_computer.*`; новый `fuel_properties.*` в том же каталоге.

Сохранить MAP/VE/температуру заряда. FuelProperties: ethanol, density(E,T), stoich, validity/source/age/generation. Перенести live→stored→fallback и preload; добавить CRC/age/refuel policy. Один snapshot обслуживает пуск, afterstart, прогрев, Film, DI/PI, HPFP, угол и boost; исключить двойную IAT-компенсацию.

**Готово, когда:** 500 mg воздуха /14.7 /lambda1 =34.013605 mg; при .8 =42.517007 mg. Потеря/возврат Flex, NaN, cold boot и заправка не расходят состав между потребителями. Reference flow и плотность согласованы; память backup не считается гарантированно постоянной.

### ECU-06 · Независимые модели двух групп и SPA

**P0** · Зависимости: 01, 05 · R 2D deadtime + FS SPA; EMU zero-dose [R1](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) [F1](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197) [E1](evidence_manifest.md#e1)

**Артефакт:** Расширить `C/algo/fuel/injector_model.*`; новые `InjectorGroupConfig`, `GroupDoseResult`.

Группа, физическая рампа и насос - разные объекты. У DI/PI свои pressure source, characterization, Preset/Custom, outputs[6], минимум дозы и timing. PI: масса→объём→effective→SPA→deadtime; DI использует свою характеристику без двойного lag. Малую дозу вернуть как infeasible, не округлять скрыто вверх.

**Готово, когда:** 600 mL/min, 20 µL, SPA=-0.1 ms, DT=0.8 ms дают 2.0/2.7 ms. Нулевая доза = no-event; .4 µL при min1 µL = deficit. Изменение PI-кривой не меняет DI; SPA учитывает дозу конкретного цилиндра, монотонность и границы проверены.

### ECU-07 · Один STFT с картами полномочий

**P1** · Зависимости: 01, 04, 05; интеграция 08-10 · G карты + F relative error; R gates [G1](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/math/closed_loop_fuel_cell.cpp#L69) [F3](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel_cell.cpp#L34) [R11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel.cpp#L102)

**Артефакт:** Существующие `C/math/closed_loop_fuel*.cpp`; новая schema трёх карт RPM×load.

Перенести maxAdd/maxRemove/timeConstant; вычислять load один раз. Для новой калибровки выбрать measured/target−1 с явной миграцией gains/знаков. Сохранить gates/deadband, hold/reset/recovery и задержку измерения после cut/ALS/DFCO/shift. LTFT и дополнительные банки исключены.

**Готово, когда:** 0.88/0.80−1=+0.10. Коррекция ограничивается текущей ячейкой, target≤0 и отказ lambda не накапливают trim. Intentional cut не вызывает ложное обогащение; отпускание без скачка. Нижняя timeConstant определяется задержкой системы, а не 0.01 s донора.

### ECU-08 · PI Fuel Film с target/rise/fall

**P1** · Зависимости: 01, 05, 06; интеграция 09, 10 · Наш закон; R mass balance; EMU A/UI [R12](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/wall_fuel.cpp#L15) [G2](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/algo/wall_fuel.cpp#L76) [E1](evidence_manifest.md#e1) [E8](evidence_manifest.md#e8)

**Артефакт:** Новый `C/algo/fuel/target_film.*`; existing `wall_fuel.cpp` как контрольный образец в тестах.

Выбрать конечный по времени переход к цели. Цель: offset+RPM×EfficiencyLoad и CLT/charge/lambda/RPM/custom corrections; rise/fall по load с corrections. Per-cylinder PI state, instant limit; accelerator-reset сбрасывает correction integrator, не стирает физическую плёнку. Есть feedback committed dose; DI не получает PI-плёнку.

**Готово, когда:** 100→140 µL за200 ms при dt10 ms: +2 µL, при rho.72 это1.44 mg. Ограничение1 µL не публикует изменение2 µL. Cut, PI share→0→1 и restart сохраняют баланс массы. XML261.2 имеет 1D base+RPM correction; наш 2D закон не объявляется копией EMU.


<!-- page break -->

## 09-12 · Доза, независимые события и два ТНВД

### ECU-09 · Распределитель массы DI/PI

**P0** · Зависимости: 04-06; интеграция 08 · Новая реализация; EMU dispatch только A [R2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) [E1](evidence_manifest.md#e1) [E2](evidence_manifest.md#e2)

**Артефакт:** Новый `C/algo/fuel/fuel_allocator.*`; `CylinderFuelRequest` / `GroupDoseResult`.

Шесть топливных trims RPM×load применяются к общей массе до split. Доля DI/PI - предпочтение, ограниченное minimum dose, давлением, DI-window и PI-duty. Ограниченное число проходов уточняет capacity; разрешённый перенос дефицита идёт только в проверенный запас другой группы.

**Готово, когда:** 20 mg с DI60% дают12+8 mg. При PI unavailable: DI20 либо явный unmet, никогда молчаливые12. Ledger requested=plannedDI+plannedPI+unmet с отдельным transient balance; запрещены скрытая потеря массы и бесконечный перерасчёт.

### ECU-10 · Независимые угловые события DI/PI

**P0** · Зависимости: 03, 04, 06, 09 · R scheduler + новая интеграция [R2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) [E2](evidence_manifest.md#e2)

**Артефакт:** Изменить `C/engine_cycle/fuel_schedule.*`, `main_trigger_callback.cpp`; новый `ScheduledInjectionEvent`.

Отдельные start/end для каждой группы/цилиндра; cycle ID и cancellation generation; общий проверенный commit. Убрать обязательное совместное открытие стадий. Поддержать moving VVT, reset/stop/sync loss и поздний cut; onboard driver принимает конечное электрическое событие.

**Готово, когда:** 6000 rpm:720°=20 ms,100°=2.777778 ms; DI3 ms не помещается, хотя duty15%. После cut нет stale DI/PI события. Симулятор проверяет все12 каналов; стенд подтверждает фазу, pulse width, задержку cancel и отсутствие конфликтов с двумя HPFP.

### ECU-11 · Два фазированных ТНВД

**P0** · Зависимости: 03, 05, 09, 10 · R HPFP + новая channelization; EMU A [R3](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L61) [E2](evidence_manifest.md#e2)

**Артефакт:** Расширить `C/engine_cycle/high_pressure_fuel_pump.*`; новые `RailPressureDomain`, `HpfpChannel[2]`.

У каждого насоса свои cam/lobe/offset/output/state. Общая DI-рампа: один pressure demand и распределение; независимые рампы: собственные датчики/контуры. FF - сумма назначенной DI-массы активных событий, переводимая через плотность; PI исключён. Slew использует measured dt.

**Готово, когда:** 6×20 mg, DI60% =72 mg/100 µL при rho.72; cut одного цилиндра =60 mg/83.333333 µL. Смена фазы pump1 не двигает pump2; отказ снижает capacity. HIL/стенд подтверждают клапан/фазирование; EMU mode2/3 доказывает routing, не закон управления.

### ECU-12 · Окончательная capacity и long injection

**P0** · Зависимости: 06, 08-11; API 17 · R limp + новая проверка конечных событий [R4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L164) [R2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) [E2](evidence_manifest.md#e2)

**Артефакт:** Новый `C/algo/fuel/injection_capacity.*`; связь с LimpManager и cut executor.

Проверять каждый цилиндр/группу после trims/Film/SPA: PI duty, DI-window, min-event, max electrical hold. Различать мгновенное и длительное превышение, hysteresis/recovery. Сначала разрешённое перераспределение, затем load cap/cylinder cut обеих групп; возвращать реально назначенный результат Film/STFT.

**Готово, когда:** Выявляются перегрузка одного цилиндра и DI3 ms/100°/6000 rpm при низком среднем duty. Выход из overload не выпускает отложенный pulse. Логи различают requested, schedulable, committed и estimated mass; estimated не называется измеренной подачей.


<!-- page break -->

## 13-16 · Угол, knock и управление наддувом

### ECU-13 · Угол, переходы и шесть цилиндров

**P0** · Зависимости: 01, 04; producer 14 · R corrections + наша политика; EMU A/B [R14](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/ignition/ignition_state.cpp#L181) [E5](evidence_manifest.md#e5)

**Артефакт:** Существующие `C/algo/ignition/ignition_state.cpp`, `C/algo/engine2.cpp`, `C/engine_cycle/spark_logic.cpp`.

Сохранить CLT/IAT и cylinder trims. Определить приоритет normal/idle/overrun/ALS/launch/cranking, разрешённые поправки, advance/retard rates и zero-rate semantics. Per-cylinder knock применять один раз; проследить final angle до dwell/spark event с конечными пределами.

**Готово, когда:** 20°+trim2°−knock3°=19° при свободных limits. ALS→idle→normal и LC+ALS имеют заданную траекторию; clamp после отрицательного trim проверен. Смена RPM не меняет физический смысл °/s или °/rev. Порядок EMU остаётся B, не правилом нашей безопасности.

### ECU-14 · Два knock-входа и независимый retard

**P0** · Зависимости: 03, 04, 13 · R acquisition + FS/F health; EMU consumer [R6](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L108) [F7](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/sensors/sensor_checker.cpp#L553) [F8](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) [E5](evidence_manifest.md#e5) [E7](evidence_manifest.md#e7)

**Артефакт:** Существующие `C/engine_cycle/knock_controller.*`, `C/sensors/sensor_checker.cpp`, `impl/software_knock.cpp`.

Retard[6], sensor/cylinder gains, threshold RPM×load, окно относительно combustion TDC, frequency и реализованное время интегратора. Задать hold/recovery, ignition-cut delay и fuel/boost responses. Перенести health/debounce; добавить never-seen, no-window, ADC-busy, saturation; cut делает окно invalid.

**Готово, когда:** Knock cyl2 меняет только retard2; глобальный derate имеет свою причину. Проверены оба обрыва, чередование входов и пропуск IRQ на верхних RPM. DTC debounce не задерживает критическую защиту. EMU % нельзя напрямую сопоставлять dBv R; detection law проектируется здесь.

### ECU-15 · DBW/EWG: достоверность и два контура

**P0** · Зависимости: 03, 04 · Точечный F guard + R приводы [R13](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/electronic_throttle.cpp#L554) [F5](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L504)

**Артефакт:** Существующий `C/actuators/electronic_throttle.cpp`; новый actuator fault policy.

Перенести valid output guard для всех типов. Сохранить DBW две дорожки TPS/PPS и tracking; EWG position PID отделён от pressure PID. Задать normalized opening и H-bridge sign, endpoints, current/stall/stale faults, duty bounds/slew/deadband. Anti-windup получает фактически разрешённый выход.

**Готово, когда:** Invalid/NaN command, feedback loss, jam и saturation имеют определённый output/recovery. На стенде проверена полярность и поведение без пружины/при потере питания. Отключённый мост не считается доказанно открытым wastegate; карты не обходят DBW diagnostics.

### ECU-16 · Boost target и FF по конечной цели

**P0** · Зависимости: 04, 05, 15; caps API17 · FS axes + F table; EMU stages, наш min [F4](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/boost_control.cpp#L96) [F11](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L223) [E3](evidence_manifest.md#e3)

**Артефакт:** Существующий `C/actuators/boost_control.cpp`; тип `FinalBoostTarget` и отдельные target/FF tables.

База RPM×TPS; PPS только явным selector. Normal/ALS/launch→CLT/ethanol/gear/VSS/custom/knock corrections→caps→ramp. FF (базовое упреждающее управление) RPM×FINAL TARGET пересчитывается в том же цикле, затем pressure PID с RPM/pressure/deviation gates, I/rate bounds. Разделить absolute/gauge; cap выше рампы.

**Готово, когда:** 100×1.10×.80=88; cap80 даёт80 и сразу меняет FF. Несимметричная карта выявляет перестановку осей; TPS≠PPS проверено. EWG/turbo saturation не накапливает I. FOME getOpenLoop игнорирует target: нужная связь пишется заново; EMU min-формула не доказана.


<!-- page break -->

## 17-20 · Защиты, насосы, VVT и холостой ход

### ECU-17 · Единый supervisor всех защит

**P0** · Зависимости: 04; API рано, интеграция 12, 14-16 · R защита + F диагностика; EMU A/B [R4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L164) [R17](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/converters/turbocharger_speed_converter.h#L9) [F8](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) [E3](evidence_manifest.md#e3) [E6](evidence_manifest.md#e6)

**Артефакт:** Новые `C/modules/sport/protection_supervisor.*`; существующие LimpManager/lambda_monitor/sensor converter.

Правила lambda lean/rich/invalid; oil low/high/start; PI/DI pressure; EGT/ALS budget; CLT/IAT/oil/fuel/электроника; sync/драйверы/связь. Turbo: широкий RPM канал, timeout, cap и hard cut после control. Overboost независим: absolute MAP и превышение final target. Для каждого delay/accumulator, latch, hysteresis, recovery.

**Готово, когда:** 65535/65536/150000/250000 rpm проходят sensor→CAN/API/log без потери диапазона. MAP invalid не снимает active cut. False lean после intentional cut исключён, другие защиты активны. Fault/fault/good/fault различает timer и leaky accumulator; dt jitter не меняет физическую задержку.

### ECU-18 · VVT и компенсации hold duty

**P1** · Зависимости: 03, 04, 11 · R advanced + FS temperature/voltage [R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/vvt.cpp#L135) [F6](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/vvt.cpp#L133)

**Артефакт:** Существующий `C/actuators/vvt.cpp`; per-cam config/telemetry.

Сохранить intake/exhaust loops, oil-pressure FF и пределы. Точечно добавить OilTemp→CLT fallback, voltage hold и target ramp без двойной компенсации. Число каналов закрепить по головкам. При движении валов синхронно пересчитывать фазы HPFP.

**Готово, когда:** Voltage/temperature sweep, invalid OilTemp, упор и потеря cam имеют заданный результат. Каждый канал независимо ограничивается и диагностируется. 14/Vbat донора не универсальная модель: соответствие клапану подтверждается стендом и калибровкой.

### ECU-19 · Нативный универсальный PWM-PID

**P1** · Зависимости: 03, 04; protection API17 · Новый controller на R helpers; EMU metadata [R18](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L54) [E7](evidence_manifest.md#e7)

**Артефакт:** Новые `C/actuators/pressure_pwm_controller.*`, конфиг независимых instances.

Feedback/units, setpoint constant/table, FF, P/I/D, update rate, PWM frequency/polarity, filter, clamps, anti-windup/slew. Prime/start/run/fault и переход OL/CL. Обязательные instances: масло и LP-топливо; безопасный duty зависит от гидравлики. HPFP остаётся отдельным фазированным модулем.

**Готово, когда:** Оба контура независимо держат заданные цели на модели, затем стенде. Sensor disconnect не подставляет ноль в PID; saturation/restart/variable dt не дают скачка. Supervisor действует независимо. GPPWM table duty и EMU P/I/D metadata не считаются готовым замкнутым законом.

### ECU-20 · ХХ: быстрый угол и медленный воздух

**P1** · Зависимости: 04, 05, 13, 15; интеграция 08 · R idle/DBW + наш каскад; EMU UI/A [R5](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/idle_thread.cpp#L170) [E7](evidence_manifest.md#e7)

**Артефакт:** Существующий `C/actuators/idle_thread.cpp`; новый reserve-angle coordinator.

RPM target CLT + afterstart CLT×time, ramp-down, capture bounds/armed/exit, pedal hysteresis/blend. Быстрый RPM→угол; медленный angle reserve→air с %/° и %/(°·s). FF targetRPM×CLT и нагрузки вентиляторов/насосов; отдельное air→DBW преобразование. Anti-stall и limits согласованы.

**Готово, когда:** Cold/hot start, fan step, clutch capture и ALS exit→idle восстанавливают резерв угла без борьбы интеграторов. DBW min/max и angular limits дают anti-windup; pedal blend без ступени. Метаданные EMU подтверждают поля, но не этот закон каскада.


<!-- page break -->

## 21-24 · Спортивные режимы и нитрос

### ECU-21 · Overrun и DFCO с согласованным возвратом

**P1** · Зависимости: 04, 07-10, 13, 20 · R DFCO + новый coordinator; EMU states [R7](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/dfco.cpp#L132) [E7](evidence_manifest.md#e7)

**Артефакт:** Существующий `C/algo/fuel/dfco.cpp`; новый `C/modules/sport/overrun.*`.

Enter/Active/Exit управляет angle/DBW/fuel/cylinder cut. Разделить fuel-on и DFCO; определить приоритет idle, ALS и shift blip. Исправить interpolation так, чтобы configured duration определяла весь переход. Сохранить физическую PI-плёнку и задержку STFT после возврата.

**Готово, когда:** Рампы0/0.2/0.5/2 s завершаются по параметру; tip-in в середине Exit не даёт лишнюю дозу. DFCO создаёт no-event в обеих группах. Переход к ХХ, смена DI/PI и одновременный FFS имеют проверяемые requests/reasons; полный EMU-controller не восстановлен.

### ECU-22 · ALS с нормальным выходом и abort

**P1** · Зависимости: 04, 10, 13, 15-17; интеграция 20 · R gates + наш автомат; EMU A/B/C [R20](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/antilag_system.cpp#L38) [F10](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) [E4](evidence_manifest.md#e4)

**Артефакт:** Существующий `C/algo/antilag_system.cpp`; новые Exit/Cooldown и event-cut requests.

Disabled/Blocked/Armed/Active/Exit/Cooldown/Fault; gates CLT/EGT/APS/RPM/VSS, physical time budget. Нормальный выход координирует angle/cut/fuel/DBW/boost, аварийный снимает опасные воздействия. Не переносить FOME ungated/late-update skip и no-consecutive предел около50%.

**Готово, когда:** 0/1/99/100% cut, disabled с ненулевым ratio, pending skip, invalid EGT, повторные короткие включения и re-arm проверены. Active cap сохраняется на Exit; N2O отключается при запрете нужного топлива. EMU exit branch существует; полный exit law и timebase остаются C.

### ECU-23 · Launch, секвентальный cut и FFS

**P1** · Зависимости: 04, 10, 13, 16, 17; I/O25 · R launch/shift + новые exits [R19](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/launch_control.cpp#L73) [R8](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/shift_torque_reduction_controller.cpp#L17)

**Артефакт:** Существующие `C/algo/launch_control.cpp`, `shift_torque_reduction_controller.cpp`; новый shift state machine.

Launch Ready/Active/Exit/Re-arm: сцепление/скорость/передача, возврат по времени/скорости. Sequential: loadcell/CAN request, debounce, minimum cut, gear confirm, timeout. FFS: clutch/APS/RPM, предел раскрутки и управляемое восстановление; общий вход сцепления имеет явного владельца.

**Готово, когда:** Cut не застревает при пропаже gear confirm; новый shift требует re-arm. Конфликт launch/FFS/ALS решается таблицей приоритетов. Доли и 100% cut проходят ECU-04; ускорение на Exit ограничено действующими caps. Нативный путь не зависит от Lua.

### ECU-24 · Нитрос с согласованным топливом

**P1** · Зависимости: 04-06, 09, 10, 13, 17 · R nitrous + наша интеграция [R9](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/nitrous_controller.cpp#L11)

**Артефакт:** Существующий `C/algo/nitrous_controller.*`; связанный `NitrousRequest`.

Разрешение по RPM/педали/передаче/температуре/давлению и capacity. Добавка топлива учитывает Flex и split DI/PI, угол - отдельный запрос. Определить совместимость ALS/launch и отключение перед shift/cut; time limit/re-arm. Wet/dry, ступени и progressive зависят от комплекта.

**Готово, когда:** No-fuel или deficit необходимой дозы запрещает N2O в том же разрешённом плане. Sensor fault, shift, timeout и emergency abort гарантированно снимают output. На стенде проверена задержка физического выключения; модуль обязателен, его удаление из профиля не допускается.


<!-- page break -->

## 25-28 · Связь, телеметрия и старт клиента

### ECU-25 · Две CAN, SENT и LIN без Lua

**P1** · Зависимости: 02, 03, 04 · R transport + native device adapters; наш контракт

**Артефакт:** Существующий `firmware/hw_layer/`; новые `C/modules/sport/io_gateway.*` и device-specific adapters.

Два CAN controller с независимыми rates/filters/RX/TX/bus-off; source age/timeout для критических данных. SENT CRC/status/pause/formats; LIN master/slave, расписание и recovery по списку устройств. Для PDM/DDU/КПП реализовать C++ протоколы и логировать stale/fault.

**Готово, когда:** Нагрузка/ошибки CAN1 не блокируют CAN2 и injection events. Повреждённый SENT и LIN timeout не сохраняют старое valid значение. Протоколы и hardware timing принимаются только с выбранными устройствами; Flex/turbo capture не конфликтуют с timers.

### ECU-26 · Полная телеметрия и ECU API endpoints

**P1** · Зависимости: 02, 29; по мере 04-25 · R transport/output channels + новый API

**Артефакт:** Существующий `firmware/console/binary/output_channels.txt`; новые `firmware/console/sport_api/` и log channels.

Привязать типизированную схему ECU-29 к firmware. Все карты/оси/единицы, enum, defaults и миграция входят в каждый пакет. Публиковать requested/limited/applied, winner+all reasons, cycle/group/cylinder, fuel/film/capacity/HPFP, PID/health/timing. Реализовать snapshot/subscriptions и ring buffer до/после аварии.

**Готово, когда:** Согласованы schema hash, firmware и typed payloads. Команды проходят ECU validation; client limits не заменяют firmware checks. Backpressure/потеря подписчика не блокируют scheduler. Сервисный транспорт и проверенные библиотеки R допустимы внутри; чужой клиент не нужен.

### ECU-27 · Сквозные испытания firmware и выпуск

**P1** · Зависимости: 01-26; полный продукт после28-37 · Новый regression/HIL пакет на инфраструктуре R

**Артефакт:** Новые `unit_tests/tests/sport/`, `simulator/sport_scenarios/`, `docs/sport/release_evidence.md`.

Ранние fixtures появляются с ECU-01; закрытие после math→simulator→HIL→калиброванное железо. Проверить 6DI+6PI+2HPFP, движущиеся VVT, sync loss, reset, все mode exits, sensor/driver faults и насыщения. Фиксировать worst-case execution/latency и память на целевой сборке.

**Готово, когда:** Ноль событий вне разрешённого окна и ноль неотменённых stale pulses. Измеренные бюджеты timing/CPU/ADC соответствуют hardware contract. Выпуск содержит firmware+собственный клиент+schema+логи стенда+ограничения калибровки; host tests сами по себе не разрешают мотор.

### ECU-28 · Прототип UX и выбор стека клиента

**P0** · Зависимости: 01; параллельно02/04 · Наш UX; R tuner как кандидат reuse [U1](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/readme.md#L1) [U2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292)

**Артефакт:** Новые `client/prototypes/`, `docs/client/ux_flows.md`, `stack_decision.md`.

Спроектировать с тюнером путь: подключить→найти карту→изменить→применить→записать лог→сравнить. Windows предложена первой платформой по текущей среде; ОС окончательно выбрать в прототипе. Сравнить reuse rusEFI tuner и новый frontend; Qt/Tauri заранее не назначать. Проверить клавиатуру, diff карт и связь лога с рабочей ячейкой/причиной ограничения.

**Готово, когда:** Пройден путь на симуляторе с тюнером, замечания зафиксированы. Измерены edit/render/log и память; выбраны стек, первая ОС и бюджеты37. Собственный продукт допускает fork/reuse открытого UI/backend. Вертикальный срез готов без мотора; другие ОС не обещаны.


<!-- page break -->

## 29-32 · Собственный клиент: API, проекты, карты

### ECU-29 · Общая схема и транзакционный протокол

**P0** · Зависимости: 01, 02; согласование28 · F generator + R wire layer; новый контракт [U4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288) [U5](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java)

**Артефакт:** Новые `shared/schema/`, `tools/schema_codegen/`, `docs/protocol/sport_api.md`; адаптация existing ConfigDefinition.

Один источник: ID/type/scale/endian, карты/оси, units/ranges/enum/defaults, channels/actions. Reuse parser/layout и C/Java writers; добавить descriptors и заменить runtime INI provider. Handshake device/board/firmware/schema/capabilities; read/snapshot/subscribe, staged apply→validate→commit, generation/transaction ID, atomic groups/CRC.

**Готово, когда:** Client и ECU независимо отвергают неверные значения/версии. Повтор request не дублирует commit; разрыв до/после commit разрешается чтением generation/hash. Карта не применяется по частям. INI не используется основным контрактом; транспорт R можно адаптировать за API.

### ECU-30 · Подключение и состояние сессии

**P0** · Зависимости: 28, 29; mock26 · R BinaryProtocol/autodetect + наш adapter [U4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288)

**Артефакт:** Новые `client/connection/`, `client/device_session/`, mock ECU server.

Обнаружение доступных интерфейсов, connect/disconnect, идентификация платы, firmware и capabilities; понятные Offline/Connecting/Online/Stale/Incompatible. Reconnect сверяет device ID и калибровку, не отправляет старые edits автоматически. Отдельные read-only/настройка/service permissions по состоянию ECU.

**Готово, когда:** Подключение к симулятору показывает версию и живой канал, читает/меняет тестовый параметр через validation/commit. Wrong device, timeout, duplicate packets, reconnect и firmware mismatch дают явный результат. Пользователь всегда видит, с каким ECU и проектом работает.

### ECU-31 · Проекты и калибровки offline/online

**P1** · Зависимости: 28-30 · Новая модель данных и рабочий интерфейс

**Артефакт:** Новые `client/projects/`, `client/calibration/`, versioned project format.

Открытие/сохранение/копия проекта, ECU snapshot и локальная рабочая версия; diff по параметрам/ячейкам, undo/redo, pending changes и выбор apply. Миграция schema с отчётом потерь/замен; совместимость hardware/capabilities. Runtime apply отделён от явного сохранения во flash.

**Готово, когда:** Offline edit→connect→compare→validate→apply→save→reopen сохраняет значения. Конфликт удалённой generation не затирается; invalid поля видны до commit. Disconnect не теряет локальные правки; rollback/undo и миграция тестируются на версиях N/N−1 и неизвестной версии.

### ECU-32 · Удобный редактор карт и таблиц

**P1** · Зависимости: 28, 29, 31 · Наш UX; reuse R table/3D widgets [U2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292)

**Артефакт:** Новые `client/editors/table2d/`, `table3d/`, `axis_editor/`.

Адаптировать TuningTableView/Surface3DView или их операции в выбранный стек, заменив IniFileModel нашей schema. 2D/3D: диапазон ячеек, keyboard, copy/paste, undo, scale/offset, явная интерполяция. Оси/единицы видны, validate monotonic bins/limits/topology. 3D связан с точными ячейками; live cursor данные не меняет.

**Готово, когда:** Несимметричная карта сохраняет X/Y после save/ECU roundtrip. Массовая правка показывает diff и отменяется; paste вне диапазона отклоняется. Из точки лога можно перейти к рабочим ячейкам нужной карты и сравнить версии; DI/PI/STFT/Film сценарии сохраняют точность и единицы.


<!-- page break -->

## 33-36 · Графики, логи, сервис и обновление

### ECU-33 · Живые панели, графики и причины состояний

**P1** · Зависимости: 28-30, 26 · Собственный интерфейс к typed telemetry

**Артефакт:** Новые `client/live/`, `client/channel_browser/`, dashboard layouts.

Поиск/группы каналов, значения/единицы/quality/age; configurable dashboards и time graphs. Показывать current mode/state, winner+all reasons, requested/limited/applied, PID/film/DI-PI capacity. Decimation/ограничение истории отделить от сохранённого raw log; stale канал маркировать, не показывать как текущий.

**Готово, когда:** Сценарии overload/ALS Exit/invalid sensor объяснимы по панели без чтения firmware. High-rate telemetry не блокирует редактирование; остановка потока сразу видна. Графики синхронизированы по ECU time; проверены разрыв, переполнение очереди и возврат связи.

### ECU-34 · Логгер и просмотр с наложением заездов

**P1** · Зависимости: 29-31, 33 · R parser/viewer + наша schema/log связь [U3](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java#L189) [U7](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/logview/BinaryLogReader.java#L13)

**Артефакт:** Новые `client/logging/`, `client/log_viewer/`; schema-aware log index.

Запись channels с ECU time, schema/firmware/project ID, quality/events. Reuse R LogViewerPanel и MLVLG v2 parser в пределах формата; заменить INI-связь log↔map. Offline zoom/cursors/axes, поиск аварии, overlay с явным alignment; сохранять старую schema. Не наследовать неоднозначность16-bit timestamp при длинных паузах.

**Готово, когда:** Лог читается после потери питания клиента/обрыва до последнего целого блока; пропуски отмечены. Overlay не совмещает разные шкалы молча. Тестовый поток и события воспроизводятся без незаявленной потери; длинный лог открывается в бюджете прототипа28.

### ECU-35 · Диагностика, trigger scope и сервис

**P1** · Зависимости: 03, 26, 29, 30 · Собственная сервисная UI + проверенные ECU hooks

**Артефакт:** Новые `client/service/`; firmware actions через `sport_api/`.

Fault history/first reason, sensor/driver health, counters; trigger/crank-cam scope с export. Actuator tests для DBW/EWG/PWM/injector/pump имеют явный service state, разрешённые диапазоны, время и stop. ECU проверяет состояние двигателя/питания и доступность выхода независимо от UI.

**Готово, когда:** Запрещённая сервисная команда отклоняется ECU и объясняется в UI. Потеря связи/timeout прекращает test, restore не запускает его повторно. Scope capture/export не мешает scheduler. Каждый исполнитель проверяется mock/HIL до сервисной работы на реальном узле.

### ECU-36 · Обновление firmware и восстановление

**P1** · Зависимости: 03, 29, 30; bootloader contract · F DFU orchestration + наш workflow [U6](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_console/ui/src/main/java/com/rusefi/maintenance/DfuFlasher.java#L25)

**Артефакт:** Новые `client/updater/`, firmware package manifest и board-specific recovery adapter.

Проверять board/device/schema и пакет; сохранить калибровку/план миграции. F DfuFlasher даёт orchestration, но использует внешний STM32 CLI и фиксированные адрес/usb1/full erase: их не переносить. Наши transfer/verify/activate/reconnect/recovery зависят от bootloader/flash layout; A-B/rollback не предполагаются.

**Готово, когда:** Отказ/обрыв на каждой стадии не выдаёт ложное «готово»; после reconnect проверены running firmware и calibration hash. Recovery подтверждён на целевой плате. Несовместимый пакет не активируется; update запрещён при работающем двигателе самим ECU.


<!-- page break -->

## 37-38 · Общий выпуск и дополнительные функции

### ECU-37 · Приёмка собственного клиента с ECU

**P1** · Зависимости: 28-36; firmware27 · Новый protocol/GUI integration suite

**Артефакт:** Новые `client/tests/`, `tests/protocol/`, `docs/client/release_evidence.md`.

Проверить UX-сценарии прототипа, typed-schema roundtrip, disconnect/reconnect, N/N−1/unknown versions, staged commit, logging и update recovery. Simulator входит в CI; HIL проверяет реальные transport limits. Проверить редактирование на фоне максимального согласованного потока, длительные сессии и доступность ошибок.

**Готово, когда:** Все обязательные операции доступны собственным клиентом без TunerStudio/FOME Console. Performance соответствует измеримым бюджетам28; version matrix опубликована. Релиз37+27 закрывается совместно: firmware, desktop installer, schema, калибровка и инструкции восстановления согласованы.

### ECU-38 · Дополнения после обязательного выпуска

**P2** · Зависимости: 27, 37; частные API04/15/25 · Исторический G + наш дизайн; выборочный reverse [G3](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/actuators/electronic_throttle.cpp#L649) [E9](evidence_manifest.md#e9)

**Артефакт:** Новые native mode profiles/TC/pit; `docs/sport/reverse_followups.md` только по принятому вопросу.

Несколько pedal maps, Track/Drift/Wet, pit limiter и TC при наличии скоростей. G selector перенести до update и включить в unit path; redundancy bypass не брать. Ограниченные reverse-вопросы: units min-dose, выбранный Film reset или конкретный limiter helper - только если меняют решение.

**Готово, когда:** Map index/CAN timeout и переключение под педалью не обходят DBW caps. Каждый reverse follow-up имеет адрес/версию/вопрос и конечный артефакт; отсутствие ответа фиксирует нашу спецификацию, а не блокирует01-37. Полная torque-to-air модель остаётся отдельной работой; собственный клиент уже обязателен.

### Клиент входит в архитектуру продукта с первого этапа

**Общая schema → generated firmware/client models → ECU API → проект и рабочая калибровка → редакторы/live/logs/service.** Клиентский экран не является источником численных ограничений: ECU повторно проверяет значения и состояние. Настройка готовится как staged diff; atomic commit публикует целую согласованную generation. Runtime apply и сохранение во flash видны пользователю как разные операции.

Первая демонстрация не ждёт двигателя: simulator с двумя группами форсунок, mock ECU API, подключение, карта SPA или lambda target, diff/undo, validation, commit и живой график. После этого расширяется тот же путь до DI/PI, boost, knock и режимов. Производительность UI и логгера измеряется уже в прототипе на согласованном максимальном потоке, а не в конце проекта.

У rusEFI уже есть собственный rusEFI tuner и реальные редакторы карт/просмотр логов. Их можно адаптировать: BinaryProtocol и TuningTableView сейчас связаны с IniFileModel, поэтому runtime metadata adapter заменяется нашей schema. FOME generator даёт parser/layout/writers, DFU wrapper - orchestration, но не универсальный updater. Наш продукт не зависит от запуска TunerStudio или FOME Console; писать каждый виджет заново не требуется. [U1](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/readme.md#L1) [U2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292) [U3](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java#L189) [U4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288) [U5](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java) [U6](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_console/ui/src/main/java/com/rusefi/maintenance/DfuFlasher.java#L25)


<!-- page break -->

## Проверяем физические инварианты до двигателя

Четыре ступени имеют разные доказательства. Синтетический вектор проверяет выбранную спецификацию, симулятор - порядок и отмену событий, HIL - взаимодействие реальной платы с моделью, калиброванный стенд - физические выходы и устойчивость. Ни одна ранняя ступень не считается заменой последующей.

| Ступень | Обязательные проверки | Сохраняемый результат |
| --- | --- | --- |
| L1 · чистая математика | Units/finite/valid, interpolation и границы; fuel properties, SPA/min dose, Film mass ledger, STFT signs, PID saturation, physical dt, cut0/100. | Детерминированные входы/выходы и допуски. Для приведённых арифметических примеров tolerance ≤ 1e-5 в названных единицах; физическая точность этим не обещается. |
| L2 · simulator | 6×2 события +2 HPFP; crank/cam и moving VVT; late cut/reset/sync loss; concurrent mode exits; capacity и intended-cut lambda inhibit. | Trace: cycle/cylinder/group/generation/start/end/commit/cancel, source/reason; отсутствие событий вне окна и stale pulses. |
| L3 · HIL | Реальный MCU, synthetic sensor/pressure/cam; maximum configured RPM и worst-case phasing; CAN load/bus-off, SENT/LIN faults; ADC busy, driver faults. | Измеренные worst-case execution и latency; нагрузка CPU/ADC/DMA; timing budget из ECU-03, сопоставленный с осциллограммой. |
| L4 · стенд | Peak/hold, injector characterization, two HPFP, DBW/EWG polarity/jam; насосы/VVT; fuel/boost/idle/knock calibration и recovery. | Характеристики конкретных узлов, настроенные limits и реальные результаты переходов. Допуск к следующему режиму основан на измерениях. |

### Минимальный сквозной набор регрессии

| Сценарий | Наблюдаемое условие приёмки |
| --- | --- |
| DI3 ms;100°;6000 rpm | Capacity отказ/перераспределение даже при15% duty; выдаётся unmet/limit, а не скрытый clip. |
| Film fill + cylinder cut + PI disable | Нет несуществующей «впрыснутой» массы; остаточная плёнка учтена; оба scheduled paths отменены. |
| ALS Exit + shift + EGT/oil fault | Авария выигрывает; N2O off; нет residual enrichment/skip; lambda pause не отключает EGT/oil/turbo. |
| Overspeed при MAP ниже цели | Post-control ограничение действует; рост pressure PID блокируется anti-windup; пропажа turbo pulse - fault. |
| MAP invalid после overboost | Активная защита не отпускается до valid recovery; целевая рампа не обходится новым provider. |
| Один knock cylinder и два sensors | Retard адресован правильной искре; no-window не считается «нет детонации»; health отдельный по входам. |

Каждый обязательный пакет включает typed schema/API, defaults/migration, telemetry reason codes, meaningful tests и donor provenance. Клиент добавляет schema-version/disconnect/atomic-commit и UX regression, а updater - обрыв на каждой стадии и recovery. При изменении timebase сравнивается физическое время; неизвестный EMU helper не становится численным oracle.


<!-- page break -->

## Источники закреплены по версии и адресу

**R** rusEFI `5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9`. **F** FOME master `9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6`. **FS** FOME stable `343fb818014f082a14dc7dd25e69c29cfbd5bafb`. **G** ggurov/rusefi `cb7cb8528911e549c254a0339ebc06aac25ee73e`, публичная ветка 2025.04.02_gurovefi. G не характеризует нынешний epicEFI. Ссылки в карточках ведут на эти неизменяемые ревизии.

### Указатель открытого кода

[R1](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) [F1](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197) Injector model / SPA / deadtime: firmware/controllers/algo/fuel/injector_model.cpp; R L31/84/196/229, FS L197.

[R10](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/fuel_computer.cpp#L22) [F2](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12) [G1](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/math/closed_loop_fuel_cell.cpp#L69) [F3](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel_cell.cpp#L34) [R11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel.cpp#L102) FuelProperties/STFT: fuel_computer.cpp L22/L12; closed_loop_fuel_cell.cpp G L69, F L34/58; closed_loop_fuel.cpp R L102.

[R12](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/wall_fuel.cpp#L15) [G2](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/algo/wall_fuel.cpp#L76) [R2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) [R3](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L61) Film/schedules/HPFP: wall_fuel.cpp; main_trigger_callback.cpp L64/94/166; high_pressure_fuel_pump.cpp L61.

[F4](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/boost_control.cpp#L96) [F5](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L504) [F11](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L223) [R4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L164) [R17](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/converters/turbocharger_speed_converter.h#L9) Boost/guards/protections: boost_control.cpp FS L96; electronic_throttle.cpp F L504; limp_manager.cpp F L223/247, R L164/226/265; turbo converter R L9.

[F6](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/vvt.cpp#L133) [R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/vvt.cpp#L135) [F7](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/sensors/sensor_checker.cpp#L553) [F8](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) [R6](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L108) VVT/knock: vvt.cpp FS L133/174 и R L135; sensor_checker.cpp FS L553, F L261/716; knock_controller.cpp R L108.

[F9](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13) [F10](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) [G3](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/actuators/electronic_throttle.cpp#L649) [R19](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/launch_control.cpp#L73) [R20](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/antilag_system.cpp#L38) [R8](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/shift_torque_reduction_controller.cpp#L17) [R9](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/nitrous_controller.cpp#L11) Арбитр/режимы: torque_model.cpp F L13/73; spark_logic.cpp F L429; electronic_throttle.cpp G L649; launch/antilag/shift/nitrous R.

[R5](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/idle_thread.cpp#L170) [R7](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/dfco.cpp#L132) [R13](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/electronic_throttle.cpp#L554) [R14](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/ignition/ignition_state.cpp#L181) [R18](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L54) [R16](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/hellen/alphax-4K-GDI/board_configuration.cpp) [R21](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/docs/firmware-flash-usage.md) ХХ/DFCO/приводы/профиль: idle_thread.cpp L170/299; dfco.cpp L132; electronic_throttle.cpp L554/918; ignition_state.cpp L181; gppwm_channel.cpp L54; board и build profile.

### Открытые компоненты собственного клиента

[U1](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/readme.md#L1) [U2](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292) [U3](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java#L189) [U4](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288) R java_console: readme.md L1; TuningTableView.java L946/1027/1292; LogViewerPanel.java L189/752; BinaryProtocol.java L250/288/796/954. Редактор/протокол используют IniFileModel; базовый viewer допускает ini=null, связь с картой требует своего adapter.

[U5](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java) [U6](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_console/ui/src/main/java/com/rusefi/maintenance/DfuFlasher.java#L25) [U7](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/logview/BinaryLogReader.java#L13) F java_tools/configuration_definition/ConfigDefinition.java: layout и C/Java writers. F DfuFlasher.java L25/180: внешний STM32 CLI, фиксированные адрес/erase. R BinaryLogReader.java L13: MLVLG v2, ограничения timestamp. Это статически проверенные кандидаты; запуск и performance ещё не выполнены.

### Прежний реверс EMU PRO: локальная адресная опора

Корень сохранённого проекта:
Прежнее исследование EMU PRO; см. evidence_manifest.md

[E0](evidence_manifest.md#e0) [E9](evidence_manifest.md#e9) [E10](evidence_manifest.md#e10) engine_logic/README_RU.md L3/13/25-31; DECODER_NOTES_RU.md L19-55; version_comparison/REPORT_RU.md L28-40/83-88. Образ261.2, AVR32 BE, база0x80004000. Равенство выбранных функций с261.1 не доказывает весь алгоритм.

[E1](evidence_manifest.md#e1) [E2](evidence_manifest.md#e2) FUEL_RU.md L5-26/76-153: pipeline0x800278DC, dose0x80025310, min0x8002549C, deadtime0x80025AAC. GDI_RU.md L5-88: dispatch0x8002B29C, mode2 pressure1 / mode3 pressure2; controller0x8002A864 остаётся C.

[E3](evidence_manifest.md#e3) [E4](evidence_manifest.md#e4) [E5](evidence_manifest.md#e5) [E6](evidence_manifest.md#e6) BOOST_RU.md L3-59:0x800422D0, post-cap0x8004154C (формула B, applicability C). ALS_RU.md L53-111: exit0x800381E0, полный закон C. IGNITION_RU.md L63-81: consumer0x800431AC. PROTECTIONS_RU.md L3-115: duty0x80023CDC, lambda0x80023F28, oil0x80024278.

[E7](evidence_manifest.md#e7) [E8](evidence_manifest.md#e8) runtime_channel_map.json: idle L3353-3641, overrun L3643-3701, knock L4053-4521, pump PWM L7993-8161. project0_261_02.xml: Film L4957-4989, minimum volume L5000-5010. Эти поля - UI/metadata, не восстановленные laws.

Адреса в документе - для261.2. Между261.1→261.2 helpers сдвинуты: slew0x800469CC→0x800469DC; lambda0x8005F45C→0x8005F44C; fuel0x8005F4B8→0x8005F4A8; dispatch0x80060E88→0x80060E78. Хеши прежней проверки и полный индекс ссылок сохранены в редактируемом Markdown; бинарник повторно не исследовался.


## Полный индекс ссылок и идентификаторы образов

SHA256 261.1: `b85fbcf479613febef3504b838b0c6c0403d151a6160b0a7044ceee610b7b96c`; 261.2: `d349ce87bf10f6511ab8aedebeb35a85f2be0543fec01188b022a40ed4e407d8`. Это результаты сохранённой проверки, не новый пересчёт.

**R1** [rusEFI: модели форсунок, 2D deadtime, DI; L31/84/196/229](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31)

**R2** [rusEFI: конечный впрыск и одновременное открытие стадий; L64/94/166](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64)

**R3** [rusEFI: одноканальный HPFP; L61](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L61)

**R4** [rusEFI: overboost valid/latch, масло, duty; L164/226/265](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L164)

**R5** [rusEFI: ХХ и два исходных RPM-регулятора; L170/299](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/idle_thread.cpp#L170)

**R6** [rusEFI: общий retard; L108](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L108)

**R7** [rusEFI: DFCO, параметр рампы и фиксированные 0.5 s; L132](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/dfco.cpp#L132)

**R8** [rusEFI: нативный FFS / shift torque reduction; L17](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/shift_torque_reduction_controller.cpp#L17)

**R9** [rusEFI: нативный nitrous; L11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/nitrous_controller.cpp#L11)

**R10** [rusEFI: массовая модель топлива; L22](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/fuel_computer.cpp#L22)

**R11** [rusEFI: STFT gates; L102](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel.cpp#L102)

**R12** [rusEFI: X-tau mass balance и Flex corrections; L15/104/139](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/wall_fuel.cpp#L15)

**R13** [rusEFI: actuator output; EWG PID L918](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/electronic_throttle.cpp#L554)

**R14** [rusEFI: CLT/IAT ignition corrections; L181](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/ignition/ignition_state.cpp#L181)

**R15** [rusEFI: advanced VVT с oil-pressure FF; L135](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/vvt.cpp#L135)

**R16** [rusEFI: исходная конфигурация Power4GDI](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/hellen/alphax-4K-GDI/board_configuration.cpp)

**R17** [rusEFI: turbo RPM converter; output_channels.txt L221](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/converters/turbocharger_speed_converter.h#L9)

**R18** [rusEFI: GPPWM table duty; L54](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L54)

**R19** [rusEFI: launch; L73, limiter L202](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/launch_control.cpp#L73)

**R20** [rusEFI: ALS gates/requests; L38](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/antilag_system.cpp#L38)

**R21** [rusEFI: профиль и генерация через prepend.txt](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/docs/firmware-flash-usage.md)

**F1** [FOME stable: SmallPulseAdder; L197](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197)

**F2** [FOME master: сохранённый Flex helper; L12](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12)

**F3** [FOME master: relative lambda error; L34/58](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel_cell.cpp#L34)

**F4** [FOME stable: selectable boost axes; L96](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/boost_control.cpp#L96)

**F5** [FOME master: общий outputValue guard; L504](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L504)

**F6** [FOME stable: temperature hold и voltage; L133/174](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/vvt.cpp#L133)

**F7** [FOME stable: knock low-noise health; L553](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/sensors/sensor_checker.cpp#L553)

**F8** [FOME master: DtcDebouncer; L261/716](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261)

**F9** [FOME master: request/limit architecture и 90 Nm/(g air); L13/73](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13)

**F10** [FOME master: небезопасный ALS skip path; L429](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429)

**F11** [FOME master: boost-cut table, getOrZero MAP; L223/247](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L223)

**G1** [gurovefi: STFT authority/time-constant maps; L69](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/math/closed_loop_fuel_cell.cpp#L69)

**G2** [gurovefi: tau/beta MAP x RPM и enable; L76/137](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/algo/wall_fuel.cpp#L76)

**G3** [gurovefi: pedal-map selector после update; L649](https://github.com/ggurov/rusefi/blob/cb7cb8528911e549c254a0339ebc06aac25ee73e/firmware/controllers/actuators/electronic_throttle.cpp#L649)

**E0** [EMU: версия, архитектура и A/B/C; README L3/13/25-31](evidence_manifest.md#e0)

**E1** [EMU 261.2: FUEL L5-26/76-153; pipeline 0x800278DC](evidence_manifest.md#e1)

**E2** [EMU 261.2: GDI L5-88; dispatch 0x8002B29C](evidence_manifest.md#e2)

**E3** [EMU 261.2: BOOST L3-59; 0x800422D0 / 0x8004154C](evidence_manifest.md#e3)

**E4** [EMU 261.2: ALS L3-37/53-111; exit 0x800381E0](evidence_manifest.md#e4)

**E5** [EMU 261.2: IGNITION L3-93; cylinder consumer 0x800431AC](evidence_manifest.md#e5)

**E6** [EMU 261.2: PROTECTIONS L3-115; duty/oil/lambda](evidence_manifest.md#e6)

**E7** [EMU 261.2: runtime metadata; idle L3353, overrun L3643, knock L4053, pumps L7993](evidence_manifest.md#e7)

**E8** [EMU 261.2 XML: Film L4957-4989, injectors L5000-5010, fail-safe L5167-5172](evidence_manifest.md#e8)

**E9** [EMU decoder limits: L19-55; FPU/условные store](evidence_manifest.md#e9)

**E10** [EMU version comparison: hashes L28-40, fuel/GDI L83-88](evidence_manifest.md#e10)

**U1** [rusEFI tuner: собственный клиент уже существует; README L1](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/readme.md#L1)

**U2** [rusEFI: редактор карт/осей и зависимость от IniFileModel; L946/1027/1292](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292)

**U3** [rusEFI: реальный viewer timeline/histogram/scatter; L189/752](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java#L189)

**U4** [rusEFI: connect/read/write/burn/poll; текущий INI provider L288](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288)

**U5** [FOME: parser/layout/C+Java writers и hash исходных definitions](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java)

**U6** [FOME: DFU orchestration; внешний CLI/адрес/erase L21/180](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_console/ui/src/main/java/com/rusefi/maintenance/DfuFlasher.java#L25)

**U7** [rusEFI: MLVLG v2 parser, 16-bit timestamp caveat; L13](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/logview/BinaryLogReader.java#L13)


## Сопоставление исходных исследовательских задач

| Заметки | Консолидированные пакеты |
|---|---|
| fork F01/F11 | 01/02/04 |
| fork F02/F03/F04/F05/F06 | 07/06/05/08/38 |
| fork F07/F08/F09/F10 | 16/17/15/18/14 |
| fuel F0/F1/F2/F3 | 01/06/05/06 |
| fuel F4/F5/F6/F7/F8 | 09/10/08/11/07/12 |
| modes D01/D02/D03/D04 | 04/16/15/17 |
| modes D05/D06/D07/D08 | 22/13/14/20 |
| modes D09/D10/D11/D12 | 21/17/12/17/19 |
| Дополнения из обязательного ТЗ | 03/18/23/24/25/26/27 |
| Прямое уточнение пользователя: полностью свой удобный клиент | 28-37, изменения02/26/27 |
