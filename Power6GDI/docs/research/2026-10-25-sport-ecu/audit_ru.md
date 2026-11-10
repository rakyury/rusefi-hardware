# Сохраняем rusEFI и достраиваем спортивную логику

Сопоставление рабочего ТЗ с rusEFI и FOME | 25 октября 2026
Решение по базе, матрица покрытия, точечные доноры и приёмка

**Базой firmware следует оставить rusEFI на ревизии 5a42c8b3, а FOME использовать для небольших проверяемых переносов. Собственный удобный клиент без зависимости от TunerStudio и INI обязателен.** rusEFI уже содержит массовую MAP/VE-модель, 2D deadtime, DI-линеаризацию, STFT с блокировками, нативные launch/FFS/nitrous, VVT, ХХ, DBW/EWG и основу защит. Переход целиком на FOME не закрывает независимые DI/PI, два ТНВД, поцилиндровый knock retard и согласованный выход режимов. В нескольких местах он заменил бы более подходящий код менее подходящим. Самые сильные доноры - табличный Short Pulse Adder и сохранённая оценка Flex Fuel; оси boost, диагностика и VVT полезны точечно. Новая firmware-логика строится поверх имеющихся драйверов, scheduler и PID; клиент получает собственные schema/API и UX. Это решение по исходникам, а не подтверждение готовности на железе. ([R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31), [R13](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel.cpp#L102), [R21](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/shift_torque_reduction_controller.cpp#L17), [R29](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/nitrous_controller.cpp#L11), [F02](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12), [S08](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197))

### Основа есть; решающие пробелы находятся между подсистемами

Критический путь разработки: независимые DI/PI и Film; два фазированных ТНВД; поцилиндровое knock-воздействие; thermal/turbo policies; native PWM-PID и выбранный LIN; единый режимный coordinator с выходом и восстановлением. Факт наличия PID, входа или настройки не закрывает этот путь. [R10](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) [R11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L61) [R31](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L19) [R39](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L49) [R42](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/kline.cpp#L1)

Аудит сопоставляет рабочее ТЗ v0.2 от 25 октября 2026 года: 6 цилиндров, 6 DI и опционально 6 PI, 2 ТНВД, DBW + EWG, впускной/выпускной VVT, 1 lambda, 1 EGT, 2 knock, Flex Fuel, turbo limiter, 2 CAN, SENT, LIN, native PWM-PID и собственный клиент настройки/диагностики. Lua и LTFT исключены. Нитрос, режимы и защиты обязательны. Здесь «есть» означает прослеженный путь в исходниках, а не только файл/enum и не совпадение всех экранов настройки.

### Что этот документ подтверждает

Дата фиксации: 25 октября 2026, Europe/Kiev. rusEFI: **5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9**. FOME master: **9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6**. Проверенный FOME stable release_260501_02: **343fb818014f082a14dc7dd25e69c29cfbd5bafb**. Stable проверялся только для отдельно указанных доноров; слово master не является обещанием готового выпуска. Позднейший HEAD rusEFI 4956c121 изменил относительно baseline только три PNG разъёмов; выводы остаются привязаны к baseline. [C01](https://github.com/rusefi/rusefi/compare/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9...4956c1212ec8414450d699e6a74e0949f3a27c5e)

Не выполнены сборки прошивок, unit/simulation runs новой реализации, bench/HIL, проверка электрической схемы, токовых профилей, pinmux/DMA или нагрузка MCU. Точное поведение коммерческого ECU по скриншотам не доказано; скрытые поля и внутренние формулы не восстанавливались. Числа со скриншотов - примеры, а не рекомендуемые пороги, частоты или калибровки двигателя. Проценты готовности, экономии кода/памяти и сроки без реализации и измерений не приводятся.

## Матрица отделяет наличие кода от решения для проекта

53 строки охватывают обязательное ТЗ, включая собственный клиент, и отдельно помеченные предложения. Дублирующиеся требования объединены: например EGT/ALS и turbo/boost. Смешанные метки относятся к разным частям одной строки. R/F/S в ссылках означают pinned rusEFI, FOME master и проверенный FOME stable соответственно.

| Статус | Смысл |
| --- | --- |
| R - использовать имеющееся | Рабочий путь в rusEFI уже даёт основу требования; остаются конфигурация, калибровка и проверка платы. |
| R+ - переработать / расширить | Нужная функция частично есть, но её схема, состояние, wiring или границы не соответствуют полному ТЗ. |
| F - конкретный донор FOME | Есть точный переносимый алгоритм/проверка. Метка не означает перенос подсистемы целиком. |
| N - новая политика / модуль | Новая логика поверх существующих Sensor/PID/PWM/CAN/scheduler; не переписывание RTOS и драйверов. |
| ? - не проверено | Соответствие не установлено данным аудитом. «Не найдено в проверенных путях» не равно доказанному отсутствию во всех ветках. |

### Три ограничения, определяющие архитектуру

**Staged injection не равен независимому DI+PI.** Обе ветки открывают две стадии одновременно, а Fuel Film применяется к общей массе до split. HPFP берёт общую массу цилиндра 0, умноженную на число цилиндров, а не сумму выделенной DI-дозы. Поэтому второй pin или новая staging map не решают требование. [R10](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) [F10](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/fuel_schedule.cpp#L92) [R11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L61) [F11](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L73)

**Поцилиндровое измерение knock не равно поцилиндровому действию.** Оба controller хранят общий m_knockRetard; нужны независимые состояния и весь путь до окончательного угла цилиндра. Аналогично название LimpLevel1/2 в FOME не доказывает многоступенчатое ограничение мощности. [R31](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L19) [F31](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/knock_controller.cpp#L43) [F34](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261)

**Общий код DBW/EWG не доказывает безопасность EWG.** Два PID уже подключены, но non-ETB status path и механика привода требуют отдельной политики. Для EWG без возвратной пружины отключение тока не означает открытие заслонки. [R20](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/electronic_throttle.cpp#L258) [F20](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L290)

## Полная матрица: текущее покрытие и необходимая работа

### Топливо: сохранить массовую основу, разделить физические пути

| Требование / статус | rusEFI: что есть сейчас | FOME: факт или донор | Конкретное действие |
| --- | --- | --- | --- |
| 01 / R<br>MAP / VE / масса<br>ТЗ 2 | SpeedDensityBase и getCycleFuel дают массу воздуха и топлива на цилиндр. [R01](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/airmass/speed_density_base.cpp#L26) [R02](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/fuel_computer.cpp#L22) | Та же базовая формула; отдельного преимущества для ТЗ нет. [F02](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12) | Использовать rusEFI. MAP - абсолютное давление; lambda и stoich входят в массовый расчёт. Альтернативные MAF/Alpha-N исключить из профиля. |
| 02 / R<br>Температура и прогрев<br>ТЗ 2 | CLT/IAT charge model, rate limits, инициализация; отдельные CLT/IAT fuel curves. [R03](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/speed_density.cpp#L24) [R04](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/engine2.cpp#L98) [R05](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel_math.cpp#L42) | Аналогичная база. [F04](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine2.cpp#L105) [F05](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel_math.cpp#L339) | Откалибровать модель заряда. Дополнительная IAT fuel correction имеет отдельный смысл и не повторяет расчёт плотности воздуха. |
| 03 / R+ / F<br>Cranking / afterstart<br>ТЗ 2 | Пуск и Flex enrichment есть; afterstart: CLT x обороты после запуска. [R05](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel_math.cpp#L42) | ASE использует CLT x runtime seconds; есть временной taper. [F04](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine2.cpp#L105) | Сохранить запуск. При требуемой оси «секунды» адаптировать lookup и схему; обеспечить непрерывность пуск -> afterstart -> прогрев. |
| 04 / R+ / F<br>Flex Fuel и отказ<br>ТЗ 2 | Датчик даёт ethanol/fuel temp. При invalid: primary stoich; cranking отдельно берёт 50%. [R06](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/flex_sensor.cpp#L8) [R02](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/fuel_computer.cpp#L22) [R05](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel_math.cpp#L42) | Master: live -> stored -> configured fallback, preload. В stable helper отсутствует. [F02](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12) [F07](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/init/sensor/init_flex.cpp#L57) [F48](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine.cpp#L94) [S02](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/fuel_computer.cpp#L50) | Обязательный модуль. Перенести единую оценку с finite/validity/age/refuel policy. Применять её согласованно к stoich, пуску, afterstart, прогреву, transient, углу и boost; задать blends/rate limits. |
| 05 / N<br>Свойства топлива<br>ТЗ 2, 3, 5 | cc/min -> g/s использует fuelDensity=0.72; коэффициент участвует и в ТНВД. [R09](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/fuel_computer.h#L39) [R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) | Та же константа. [F09](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.h#L51) | Нужен общий контракт массы/объёма/состава/температуры. Ввести FuelProperties либо документированную mass-flow калибровку; не менять одну константу изолированно. |
| 06 / R+<br>Раздельные модели DI/PI<br>ТЗ 3 | Есть flow, reference pressure, sqrt ΔP и отдельные reference/mode primary/secondary; DI table и источник давления общие. [R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) | Reference/mode общие; полной DI pressure-mass характеристики в проверенном пути нет. [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) | Две независимые модели, pressure sources, Preset/Custom и электрические типы. PI: rail-MAP; DI: собственная характеристика. Явно различать эффективную и полную длительность. |
| 07 / R<br>Deadtime Vbat x ΔP<br>ТЗ 3 | Есть настоящая 2D battLagCorrTable в конфигурации injector_s. [R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) | Только 1D Vbat curve. [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) | Сохранить rusEFI. Отдельно определить порядок DI linearization/deadtime: полную длительность не дополнять deadtime повторно. |
| 08 / F / R+<br>Short pulse adder<br>ТЗ 3 | Есть Ford dual-slope и polynomial; case INJ_SmallPulseAdder отсутствует. Secondary nonlinearity = INJ_None. [R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) | Табличный INJ_SmallPulseAdder есть в master и stable; secondary тоже INJ_None. [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) [S08](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197) | Точечный порт lookup, enum, схемы и тестов. Независимая кривая для DI и PI; задать порядок относительно deadtime. |
| 09 / N<br>Минимальная доза<br>ТЗ 3 | Политика минимальной массы не подтверждена; scheduler отбрасывает primary pulse <50 мкс. [R10](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) | Есть minimumInjectionPulseWidth до deadtime; это clamp pulse, а не min volume. [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) | Определить поведение ниже минимальной доставляемой дозы. Логировать запрос, доступную и назначенную массу; не скрывать увеличение дозы округлением вверх. |
| 10 / R+ / N<br>6 DI + 6 PI и фазы<br>ТЗ 1, 3 | Staged map, secondary pins и две длительности есть, но обе стадии открываются одновременно. [R05](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel_math.cpp#L42) [R10](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) | Общее открытие сохраняется; split injection отключает staging. [F10](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/fuel_schedule.cpp#L92) | Новый allocator и независимые DI/PI окна на имеющемся scheduler. Шесть цилиндров, до 12 форсунок. При отказе PI перераспределять только в доступную DI capacity; multi-pulse DI пока не обязателен. |
| 11 / R+ / N<br>Два ТНВД / VVT<br>ТЗ 8 | Один набор pressure/lobe/valve, общий hpfpValve; расход = масса цилиндра 0 x число цилиндров. [R11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L61) [R04](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/engine2.cpp#L98) | Одноканальный путь и аналогичный расчёт от cylinder 0. [F11](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L73) | Разделить cam/lobe/phase/output/state для двух насосов. Расход высокого давления - сумма назначенной DI-массы. Общая рампа: один pressure loop и allocator; раздельные: свои измерения/контуры. |
| 12 / R+<br>STFT: одна лямбда<br>ТЗ 4 | Интегратор, deadband, пределы и gates launch/AE/DFCO/cut уже есть. [R12](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel_cell.cpp#L9) [R13](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel.cpp#L102) | Relative error и четыре banks; gating в просмотренном пути беднее. [F12](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel_cell.cpp#L34) [F13](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel.cpp#L83) | Сохранить rusEFI; добавить ALS/shift и transport-delay recovery. Один контур корректирует суммарную массу. Относительная ошибка - отдельное изменение с перенастройкой gain/deadband; LTFT не нужен. |
| 13 / R<br>Топливные trims цилиндров<br>ТЗ 4 | fuelTrims[cylinder].table реально применяется к массе до stage split. [R05](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel_math.cpp#L42) [R04](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/engine2.cpp#L98) | Аналогичный путь. [F04](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine2.cpp#L105) | Сохранить шесть карт RPM x load. Общую поправку цилиндра применять один раз до DI/PI; индивидуальную характеристику форсунки хранить отдельно. |
| 14 / R+ / N<br>Fuel Film: семантика<br>ТЗ 5 | Есть X-tau/beta mass film с CLT/MAP/Flex, но нет требуемого target-volume/rise/fall пути. [R14](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/wall_fuel.cpp#L15) | Та же физическая X-tau основа; точное соответствие экранным настройкам не подтверждено. [F14](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/wall_fuel.cpp#L14) | Новый алгоритм выбранной семантики: offset + RPM x Efficiency load, коррекции цели, раздельные increase/decrease duration, instant max и reset. Определить Efficiency load, lambda/additional sources и единицы. |
| 15 / R+<br>Film при смешанном впрыске<br>ТЗ 3, 5 | wallFuel.adjust вызывается до разделения общей массы на стадии. [R10](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) | Тот же порядок. [F10](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/fuel_schedule.cpp#L92) | Отдельные состояния PI-плёнки по цилиндрам; DI wall-wetting только со своей моделью. Проверить смену PI fraction, DFCO, остаточную плёнку и положительную/отрицательную коррекцию; dTPS/dMAP не дублирует Film. |
| 16 / R+ / N<br>Duty / long injection / окно<br>ТЗ 3, 11 | Instant/sustained cut использует primary duty; средняя длительность вычислена до Film и trims. Есть GDI hold-time check. [R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L67) [R05](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel_math.cpp#L42) [R04](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/engine2.cpp#L98) | Аналогичный primary-duty cut. [F15](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L160) | Проверять конечное событие каждого цилиндра/группы: PI period-duty, DI угловое окно и electrical limits, сумма/зазоры импульсов. Derate до исчерпания, согласованный cylinder cut DI+PI, задержки/hysteresis/recovery. |

### Спортивные режимы: сохранить исполнение, добавить переходы и приоритеты

| Требование / статус | rusEFI: что есть сейчас | FOME: факт или донор | Конкретное действие |
| --- | --- | --- | --- |
| 17 / R+ / N<br>Launch и выход<br>ТЗ 7 | Есть PreLaunch/Launch, latch, progressive skip, fuel/spark cut. Полного Exit нет. [R16](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/launch_control.cpp#L73) | Более простое условие + delay; не улучшает основу. [F16](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/launch_control.cpp#L81) | Ready/Active/Exit/Re-arm/Fault; clutch/speed/gear gates. Возврат DBW, boost, угла и топлива по времени/скорости; общий clutch с FFS согласовать. |
| 18 / R+ / N<br>ALS и cooling<br>ТЗ 7, 11 | CLT/RPM/throttle/duration, fuel, angle и DBW wired. Нет EGT/Exit/Cooldown; skip-блок закомментирован. [R17](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/antilag_system.cpp#L38) [R18](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/spark_logic.cpp#L676) [R19](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/ignition/ignition_state.cpp#L91) [R20](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/electronic_throttle.cpp#L258) | ALS skip активен без gate ALS; EGT/duration в проверенном модуле отсутствуют. [F17](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/antilag_system.cpp#L60) [F18](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) | Сохранить rusEFI базу. Реализовать gated spark/fuel/air/boost requests, EGT validity, запрет входа, abort, time budget, cooldown/re-arm и согласованный выход. FOME ALS целиком не переносить. |
| 19 / R+<br>FFS<br>ТЗ 7 | Нативный ShiftTorqueReductionController: clutch/button, RPM/APP, timeout, gear x axis tables. [R21](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/shift_torque_reduction_controller.cpp#L17) | TorqueReductionController - исполнитель другого torque path; полноценный FFS здесь не подтверждён. [F22](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_reduction_controller.cpp#L16) | Использовать rusEFI, добавить возврат момента, re-arm и предел раскрутки. Исключить зависимость от Lua; конфликт с launch разрешать общим менеджером. |
| 20 / R+ / N<br>Секвентальная КПП<br>ТЗ 7 | Кнопка и timed/table cut есть; loadcell/gear-confirm/законченного протокола нет. Контекст up/down есть. [R21](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/shift_torque_reduction_controller.cpp#L17) [R23](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/modules/engine_state_machine/engine_state_machine.cpp#L122) | Готовый sequential shift manager не подтверждён. [F22](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_reduction_controller.cpp#L16) | ShiftStateMachine: effort/request, debounce, minimum duration, gear confirmation, timeout, recovery. Логировать причину окончания и запрещать повтор без re-arm. |
| 21 / R+ / N<br>Отсечки и общий arbiter<br>ТЗ 7, 15 | Fuel/spark hard cut, soft timing/window, hysteresis и отдельные consumers уже есть. [R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L67) [R16](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/launch_control.cpp#L73) [R04](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/engine2.cpp#L98) | Retard/cut allocator полезен; SoftSparkLimiter не даёт физические 100% cut. [F22](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_reduction_controller.cpp#L16) [F16](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/launch_control.cpp#L81) | Новый менеджер запросов/приоритетов поверх execution. Разделить progressive и hard cut, баланс цилиндров, owner/expiry/reason, режимные комбинации; аварийный запрет выше спортивных функций. |
| 22 / R+<br>Overrun / DFCO<br>ТЗ 7 | Есть Overrun/Decel/Both, условия, подавление при shift, угол/возврат и coasting air. [R24](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/dfco.cpp#L9) [R25](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/idle_thread.cpp#L37) | Базовые блоки аналогичны; в обеих ветках ramp смешивает параметр времени и 0.5 s. [F24](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/dfco.cpp#L9) | Согласовать отдельные air/spark/fuel цели и режим с разрешённым топливом. Исправить ramp, обеспечить Film-aware возврат к тяге/ХХ и явную совместимость ALS. |
| 23 / R+<br>ХХ: цель и базовый воздух<br>ТЗ 6 | CLT target, configurable ramp, FF RPM x CLT, нагрузки, dashpot, coasting, air/timing PID есть. [R25](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/idle_thread.cpp#L37) | Аналогично; return фиксирован 3 s. D-term override от rpmRate - отдельная идея. [F25](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/idle_thread.cpp#L25) | Сохранить базу; дополнить afterstart offset/delay, armed override, диапазоны захвата, pedal hysteresis, нагрузки насосов/вентиляторов и target-source. Проверить anti-stall и clutch capture. |
| 24 / N / R+<br>ХХ: каскад угла/воздуха<br>ТЗ 6 | Legacy air и timing PID оба по RPM; modeled flow делит high/low-frequency air. Это другая схема. [R25](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/idle_thread.cpp#L37) | Legacy также RPM; torque idle работает в Nm и не воспроизводит reserve-angle loop. [F25](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/idle_thread.cpp#L25) [F30](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13) | Новый быстрый RPM->spark и медленный angle-reserve->air coordinator на PID/DBW. Min/target/max angle, integrator limits, advance/retard rates, air->DBW conversion, min/max/blend и bumpless anti-windup. |
| 25 / R+ / F<br>VVT впуск/выпуск<br>ТЗ 8 | Closed loop, intake/exhaust PID, integral limits, oil-pressure FF и per-cam target. [R26](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/vvt.cpp#L87) | Temp hold FF, 14/Vbat, startup ramp 2 s и selectable axis; части есть в stable. [F26](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/vvt.cpp#L85) [S26](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/vvt.cpp#L133) | Сохранить upstream advanced. Выборочно добавить temperature/voltage/ramp, согласовав invalid-input и комбинацию FF. Проверить tracking faults и фазирование каждого ТНВД при движении валов. |
| 26 / R<br>Карты и коррекции угла<br>ТЗ 2, 4 | ignTrims[cylinder] RPM x load применяется; CLT и IAT 3D corrections есть. [R19](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/ignition/ignition_state.cpp#L91) [R04](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/engine2.cpp#L98) | Поцилиндровые карты есть; CLT только 2D, IAT 3D. [F19](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/ignition/ignition_state.cpp#L110) [F04](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine2.cpp#L105) | Сохранить все шесть карт, температурные поправки и Flex blend. Определить порядок с knock/режимными углами и финальными пределами, без двойной коррекции. |
| 27 / R+ / F<br>Boost target: оси и поправки<br>ТЗ 10 | CL target RPM x DriverThrottleIntent; OL выбираемая ось, blends, CLT/IAT и gear OL adder. [R27](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/boost_control.cpp#L79) | Независимые X/Y обеих карт; GPPWM_Tps подменён DriverThrottleIntent. Есть в stable. [F27](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/boost_control.cpp#L47) [S27](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/boost_control.cpp#L47) | Портировать selector/validation, явно разделить TPS/PPS. Добавить требуемые target blends по CLT/ethanol/gear/speed/user/knock и переключаемые карты. Указать absolute/gauge reference. |
| 28 / N / R+<br>Boost FF по текущей цели<br>ТЗ 10 | getOpenLoop(target) игнорирует target. Native computed-target source нет. [R27](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/boost_control.cpp#L79) [R28](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm_channel_reader.cpp#L9) | То же: выбранные X/Y не добавляют вычисленную цель. [F27](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/boost_control.cpp#L47) [F28](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L10) | Передать скорректированную и ограниченную цель прямо в RPM x target FF lookup. Фильтр/задержка/диагностический прогноз - собственная определённая модель, не восстановленная по скрину. |
| 29 / R+<br>Pressure PID -> EWG PID<br>ТЗ 10 | Два контура wired: boost output -> wastegate position -> etbWastegatePid. [R27](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/boost_control.cpp#L79) [R20](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/electronic_throttle.cpp#L258) | Аналогичный путь. [F27](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/boost_control.cpp#L47) [F20](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L290) | Сохранить оба PID; добавить режимы включения по RPM/давлению/ошибке, hysteresis/reset, limits и rate integrator. Anti-windup учитывает реально разрешённую EWG position и turbo ceilings. |
| 30 / R+ / F / N<br>EWG: мотор и отказ<br>ТЗ 10 | Non-ETB output проверяется раньше validity; checkStatus рано возвращает true для non-ETB. [R20](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/electronic_throttle.cpp#L258) | Validity guard для всех actuator лучше; полноценный EWG fault path всё равно не доказан. [F20](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L290) | Точечный guard + собственная fault machine. Spring/no-spring, polarity, calibration, current limit при наличии, inversion/deadband, directional duty, slew/PWM и service-only override. Обесточивание не доказывает открытие. |
| 31 / N<br>Тепловые boost ceilings<br>ТЗ 10, 11 | Температурные поправки есть, полного min-ceiling bank и turbo policy нет в проверенном BoostController. [R27](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/boost_control.cpp#L79) | Generic blends не равны safety limiter. [F27](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/boost_control.cpp#L47) | Отдельный минимум допустимых целей CLT/oil temp/IAT/EGT/user. Коррекция запроса и защитный предел различны; независимый аварийный путь остаётся. Turbo limiter - строка 42. |
| 32 / R+<br>Нитрос обязателен<br>ТЗ 12 | Нативные arming/gates/relay/fuel/retard; callback снимает N2O при forbid injection. AFR gate = lambda x gasoline stoich. [R29](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/nitrous_controller.cpp#L11) [R19](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/ignition/ignition_state.cpp#L91) | Нативный аналог в проверенных путях не найден; это не доказательство отсутствия всех внешних реализаций. | Сохранить и расширить gear/fuel pressure/duty/EGT interlocks, time limit/re-arm, shift/ALS/launch policy, progressive/stages по комплекту. Guard задать в lambda или явно определить AFR convention; согласовать Flex и DI/PI. |

### Защиты и периферия: датчик и DTC ещё не составляют защитную политику

| Требование / статус | rusEFI: что есть сейчас | FOME: факт или донор | Конкретное действие |
| --- | --- | --- | --- |
| 33 / R+<br>Два knock-входа и gain<br>ТЗ 9 | Два ADC канала поддержаны платформой; есть cylinder->sensor, m_gain, peaks и RPM/load gain. [R32](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/impl/software_knock.cpp#L73) [R33](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/proteus/knock_config.h#L8) [R31](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L19) | Аналогичная привязка и gain. [F31](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/knock_controller.cpp#L43) | Адаптировать плату и шесть цилиндров. Разделить detection/action enable, runtime/RPM gates, усиления датчика/цилиндра, лог signal/threshold/events. Нормализацию % и dBv задать явно. |
| 34 / R+ / N<br>Knock threshold и retard<br>ТЗ 9 | Threshold 1D RPM; измерения по цилиндрам, но m_knockRetard общий и getter без cylinder. [R31](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L19) | Та же 1D threshold и общий m_knockRetard. [F31](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/knock_controller.cpp#L43) | Новая RPM x ignition-load threshold map и независимый state/limit/decay по цилиндрам до final spark. Условия RPM/pedal/channel/cut delay документировать; общий максимум только для телеметрии. |
| 35 / R+ / F<br>Knock window / DSP / отказ<br>ТЗ 9 | Bandpass, RMS/dB и sampling duration есть; при занятом ADC/pending обработке окно пропускается. [R32](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/impl/software_knock.cpp#L73) [R31](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L19) | Low-noise hook по двум каналам есть и в stable; timeout включается после первого callback. [F34](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) [S34](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/sensors/sensor_checker.cpp#L553) | Привязать окно к combustion TDC, определить DSP time constant/quantization. Диагностировать saturation, missed/never-seen windows. Порт hook не закрывает отсутствие всех callbacks; учесть шум DI/ТНВД. |
| 36 / R+ / N<br>Knock fuel / boost<br>ТЗ 9 | Общий fuel trim с пределом и возвратом уже есть; поцилиндрового fuel action нет. [R31](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L19) | В просмотренном knock-controller только retard, без аналогичной fuel reaction. [F31](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/knock_controller.cpp#L43) | Добавить boost derate и требуемые коэффициенты/возврат; согласовать STFT, EGT и DI/PI capacity. Отдельно определить общую и цилиндровую область действия топлива. |
| 37 / R+<br>Lambda lean / rich / fault<br>ТЗ 11 | Lean по target+deviation RPM/load, timeout, gates/recovery. Invalid lambda считается good только для этого монитора. [R35](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/lambda_monitor.cpp#L16) | Аналогичное lean-ядро и invalid handling. [F35](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/lambda_monitor.cpp#L45) | Сохранить lean. Добавить rich-policy и sensor-fault отдельно; блокировать трактовку смеси при intentional skips, учесть доставку выхлопа и восстановление. Один датчик не даёт цилиндровую смесь. |
| 38 / R+ / F<br>Масло: давление и отказ<br>ТЗ 11 | Afterstart, running minimum и maximum по RPM/timeout; low-check требует valid pressure. [R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L67) | Есть start delay и pressure switch; invalid трактуется как достаточное давление в этом пути. [F15](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L160) | Сохранить upstream max protection; добавить temperature map, критическую ступень и отдельную sensor-fault policy. Switch/start-delay - опциональные точечные доноры. |
| 39 / R+ / F<br>Независимый overboost<br>ТЗ 11 | Fuel cut, threshold/hysteresis; активный latch держится до valid MAP recovery. [R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L67) | Master table/axes/telemetry полезны, но MAP getOrZero и фиксированные 20 kPa; stable table не найден. [F15](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L160) [S15](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/limp_manager.cpp) | Портировать только таблицу/оси. Сохранить validity/latch rusEFI, добавить absolute и target-relative ceilings, delays, soft fuel cut и recovery. Pressure PID не заменяет этот monitor. |
| 40 / R / N<br>EGT: измерение и защита<br>ТЗ 1, 11 | Есть AEM CAN / MAX3185x registration. Готовой требуемой EGT policy в limp/ALS/boost нет. [R36](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/init/sensor/init_egt.cpp#L16) [R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L67) [R17](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/antilag_system.cpp#L38) | Чтение EGT есть; полный thermal supervisor не подтверждён. [F28](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L10) [F15](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L160) | Использовать вход одного EGT; новый warning/derate/abort с time/hysteresis, thermocouple fault и cooling. ALS entry/exit согласовать со строкой 18; один EGT не даёт шесть независимых thermal limits. |
| 41 / R+ / N<br>Давление топлива и температуры<br>ТЗ 11, 13 | Есть датчики, injector/HPFP paths и SensorChecker; полный DI/PI/fault/recovery контракт не подтверждён. [R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) [R11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L61) [R34](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/sensor_checker.cpp#L169) | Аналогичные примитивы; готовая общая политика не установлена. [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) [F11](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L73) [F34](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) | Новые low/high/tracking/capacity правила DI/PI. Thermal rules CLT/charge/oil/fuel/electronics по реальным датчикам. Для каждого - validity, delay, action, latch и recovery; критический fault может сразу отключать. |
| 42 / R+ / N<br>Turbo speed / limiter<br>ТЗ 10, 11 | Frequency->RPM есть; требуемый limiter не найден. Output turboSpeed - uint16_t с подписью hz. [R37](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/converters/turbocharger_speed_converter.h#L9) [R38](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/console/binary/output_channels.txt#L221) | Те же acquisition и несоответствие telemetry. [F37](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/converters/turbocharger_speed_converter.h#L8) [F38](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/console/binary/output_channels.txt#L230) | Новый derate/overspeed/fault/recovery на SensorResult, не UI-поле. Согласовать RPM или масштабированный krpm и диапазон Sensor/UI/CAN/log; сырые RPM >65535 не помещаются в uint16. |
| 43 / N<br>Универсальный native PWM-PID<br>ТЗ 13 | GPPWM: две оси, duty table, dutyIfError и override; это не feedback PID. [R39](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L49) | GPPWM также таблица, готового PID давления не подтверждено. [F39](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L150) | Новый контроллер на Sensor/PID/PWM. Target/FF/feedback/units/rate/direction, limits/anti-windup/slew/filter, enable/open-closed/fault. Обязательны oil и LP fuel; safe duty зависит от устройства. |
| 44 / R+<br>Две CAN и протоколы<br>ТЗ 13 | Независимые pins/rate/bus state, RX и restart; повторное устройство контролируется. [R40](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/drivers/can/can_hw.cpp#L115) | Два reader/writer и baud configs тоже есть. [F40](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/hw_layer/drivers/can/can_hw.cpp#L63) | Сохранить transport; native PDM/DDU/КПП/sensors, фильтры/RX/TX, packet schedule, timeout/age, bus-off и recovery проверить на двух шинах. Данные не живут бессрочно после потери связи. |
| 45 / R+<br>SENT и импульсные входы<br>ТЗ 13 | Есть decoder, CRC statistics, TPS/pressure decode; Power4GDI включает SENT. [R41](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/drivers/sent/sent.cpp#L83) [R50](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/hellen/alphax-4K-GDI/board.mk#L8) | Надёжный donor SENT в аналогичном пути не установлен. | Использовать rusEFI, адаптировать форматы/validity/timeout. Проверить одновременные ресурсы SENT, Flex Fuel, turbo input, crank/cam и управления выходами. |
| 46 / N / ?<br>LIN выбранных устройств<br>ТЗ 13 | Найден specific Honda K-line; UART LINEN не доказывает LIN master schedule/checksum. [R42](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/kline.cpp#L1) | Готовый прикладной LIN donor не подтверждён. | Сначала список устройств/ролей/электрики. Затем native LIN layer поверх UART/transceiver: frames, schedule, checksum, validity/timeout и диагностическое восстановление. |
| 47 / R+ / N / ?<br>Кастомная Power4GDI<br>ТЗ 1 | Stock: четыре DI pins, один hpfpValve, один mc33816 SPI config, DC output metadata=1. [R43](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/hellen/alphax-4K-GDI/board_configuration.cpp#L20) | Перенос FOME не решает физическую ёмкость и разводку. | Собственный board support для 6 DI + 6 PI, 2 ТНВД, DBW + EWG, двух knock и VVT. Проверить pinmux/timer/SPI/DMA, driver instances, токовые профили/diagnostics. Железная совместимость пока не проверена. |
| 48 / R+ / F<br>Электрика, sync и fault action<br>ТЗ 11, 14 | SensorChecker знает TPS/PPS/MAP/CLT/IAT/Flex и pin faults; это не полный fault->action контракт. [R34](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/sensor_checker.cpp#L169) | Больше sensor/cam/sync checks и debounce. LimpLevel1/2 enum не доказывает отдельное derate action. [F34](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) | Выборочный порт checks/debouncer, своя таблица action/recovery. Включить driver/power/crank-cam/VVT/CAN-SENT-LIN faults; DBW dual-track/tracking. Газ+тормоз учитывать по спортивному режиму. |
| 49 / R+<br>Логи и событие<br>ТЗ 14 | DTC пишет один MLG block и кольцевой tooth history через worker. [R45](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/modules/dtc_manager/dtc_manager.cpp#L122) | Нет основания заменять upstream logger целиком. | Расширить до нужного pre/post full-signal буфера: first/all reasons, requests/allowed/actual, цилиндровые дозы/угол/knock, sensor ages и scheduler timing. Запись не блокирует timing events. |
| 50 / R+ / ?<br>CRC / watchdog / нагрузка<br>ТЗ 14 | CRC/version/size, вторая копия и watchdog API есть; board watchdog enable здесь не доказан. [R46](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/flash_main.cpp#L143) [R47](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/ports/mpu_watchdog.h#L26) | Общая инфраструктура; преимущество переноса не установлено. | Версия схемы/миграции, worst-case execution и missed events. Проверить reset/output behavior и фактическое включение watchdog выбранной платы; service build и trigger scope сохранить. |
| 51 / R+<br>Спортивный профиль без Lua/LTFT<br>ТЗ 16, 19 | Есть supported guards и prepend.txt для upstream-страниц. UI removal не гарантирует удаления кода. [R44](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/docs/firmware-flash-usage.md#L169) | FOME не требуется для удаления функций. | Согласовать firmware, свою typed schema и capabilities; убрать Lua/LTFT/лишние load modes и unused modules. Целевой продукт без TS/INI. Nitrous, launch, ALS, shift, VVT, ХХ, защиты и связь с ECU обязательны. |
| 52 / ? / N<br>Предложенные дополнения<br>ТЗ 14 | Pit-speed, Track/Drift/Wet, ручник, дополнительный TC и точные input profiles полностью не аудированы. | Доказанной полной цепочки FOME для этих пожеланий в данном аудите нет. | Это рекомендации ассистента, не подтверждённые обязательные функции пользователя. Реализовывать отдельным этапом после согласования; TC имеет явное отключение для дрифта. |
| 53 / R+ / N / ?<br>Собственный клиент обязателен<br>ТЗ 1, 19 | Есть свой tuner, protocol read/write, редактор карт и log viewer. Runtime config/table metadata связаны с INI. Полное ТЗ не закрыто аудитом. [R51](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/readme.md#L1) [R52](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288) [R53](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292) [R54](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java#L189) | TS + INI и служебная Console документированы; полный клиент по ТЗ не подтверждён. Генератор layout пригоден для адаптации. [U01](https://github.com/FOME-Tech/fome-fw/blob/master/firmware/tunerstudio/readme.md) [U02](https://wiki.fome.tech/Intro-Start-Here/HT-Updating-The-Firmware/) [U03](https://github.com/FOME-Tech/fome-fw#what-do-we-have-here) [F55](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java) | Свой клиент без TS/INI: schema/version/capabilities/API, 2D/3D, offline/online, diff/undo/save/migration, live/log viewer, diagnostics/trigger/service, update/recovery. Reuse транспорта/виджетов требует своего metadata adapter. Стек не выбран. |

## Кодовые находки ограничивают безопасный перенос FOME

Ниже короткие фрагменты проверенных тел исходников. Они показывают точный порядок вызовов; это статическое доказательство указанного ограничения, а не результат запуска на двигателе.

### ALS skip в FOME не проверяет активность ALS

```cpp
if (engine->ALSsoftSparkLimiter.shouldSkip()) {
    continue;
}
auto ALSSkipRatio = engineConfiguration->ALSSkipRatio;
engine->ALSsoftSparkLimiter.setTargetSkipRatio(ALSSkipRatio);
```

Фрагмент внутри EFI_ANTILAG_SYSTEM && EFI_LAUNCH_CONTROL не проверяет antiLagEnabled/isAntilagCondition. Ненулевой сохранённый ratio может создавать пропуски вне ALS; update выполняется после shouldSkip и обходится при continue. Этот фрагмент подтверждён и в stable. В rusEFI соответствующий ALS skip блок целиком закомментирован: он не даёт действующий skip path. [F18](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) [S18](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/engine_cycle/spark_logic.cpp#L443) [R18](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/spark_logic.cpp#L676)

### SoftSparkLimiter нельзя назначать исполнителем hard cut

```cpp
if (m_targetSkipRatio == 0 || wasJustSkipped) {
    wasJustSkipped = false;
    return false;
}
wasJustSkipped = r < 2 * m_targetSkipRatio;
```

Изначально нулевой ratio не создаёт новых пропусков. После ненулевого ratio один вызов может использовать прежнее значение из-за позднего update. Запрет последовательных пропусков ограничивает длительную долю примерно 50%, даже при request=1; это не физические 100% cut. TorqueReductionController математически достигает fraction=1, но конечный limiter остаётся этим. [F16](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/launch_control.cpp#L81) [F22](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_reduction_controller.cpp#L16)

### Выбираемые оси boost не используют вычисленную цель

```cpp
expected<percent_t> BoostController::getOpenLoop(float target) {
    UNUSED(target);
    // ... lookup по настроенным осям
}
```

Сигнатура и UNUSED(target) присутствуют в обеих ветках; комментарий обозначает опущенную часть. В просмотренных axis readers нет native current-target source. Требуемый FF RPM x ограниченная текущая цель требует нового подключения независимо от backport selectors. [R27](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/boost_control.cpp#L79) [R28](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm_channel_reader.cpp#L9) [F27](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/boost_control.cpp#L47) [F28](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L10)

### Табличная малая нелинейность - ограниченный полезный донор

```cpp
baseDuration + interpolate2d(baseDuration,
    smallPulseAdderBins, smallPulseAdderValues)
```

Это выражение case INJ_SmallPulseAdder в getBaseDurationImpl, подтверждённое в master и stable. Его перенос должен включать настройки обеих групп: Secondary::getNonlinearMode возвращает INJ_None в обеих ветках. Эту добавку нельзя переносить вместе с полным injector_model FOME, теряя rusEFI 2D deadtime/DI characterization. [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) [S08](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197) [R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31)

## Доноры FOME имеют узкую область применения

Приоритетные порты - первые два пункта. Остальные выбираются по конкретной семантике целевой версии. «Stable + master» означает подтверждённое наличие названного фрагмента в двух pinned snapshots; оно не доказывает испытанность новой интеграции. Сохранять авторские уведомления и условия исходного проекта; правовая экспертиза в аудит не входила.

| Кандидат | Статус и источник | Точный участок | Граница переноса |
| --- | --- | --- | --- |
| Short Pulse Adder | Stable + master<br>[S08](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197) [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) | InjectorModelBase::getBaseDurationImpl, case INJ_SmallPulseAdder; injector_model.cpp. | Lookup + enum/своя schema/tests и редактор клиента. Независимые группы; secondary INJ_None расширить. Не переносить весь injector model. |
| Сохранённый Flex | Только master в проверенной паре<br>[F02](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12) [F07](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/init/sensor/init_flex.cpp#L57) [F48](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine.cpp#L94) [S02](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/fuel_computer.cpp#L50) | getStoredFlexEthanolPercent / getFlexEthanolPercent / updateStoredFlexEthanolPercent; FlexEthanolPct, preload. | Сохранить caller и startup wiring; finite/CRC/validity/age/refuel. Один estimator для всех потребителей; stored value не доказательство состава после заправки. |
| Оси boost | Stable + master<br>[F27](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/boost_control.cpp#L47) [S27](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/boost_control.cpp#L47) | BoostController::getAxisValue и independent OL/CL selectors в boost_control.cpp. | Явные TPS/PPS, validation и logs; computed target в FF добавить отдельно. Схема и оси калибровки не взаимозаменяемы. |
| VVT FF/ramp | Указанные части stable + master<br>[F26](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/vvt.cpp#L85) [S26](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/vvt.cpp#L133) | vvt.cpp: temperature hold curve, 14/Vbat, startup target ramp. | Согласовать с oil-pressure FF rusEFI; invalid-sensor policy. Фиксированные 2 s при необходимости превратить в параметр. |
| DC valid-output guard | Master; stable не проверен<br>[F20](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L290) | electronic_throttle.cpp, setOutput: outputValue && (...) перед motor set. | Узкий diff. Полная EWG fault machine, hardware current limit и безопасная механика из него не следуют. |
| Knock diagnostics / debounce | Low-noise: stable + master; debounce проверен master<br>[F31](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/knock_controller.cpp#L43) [F34](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) [S34](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/sensors/sensor_checker.cpp#L553) | Knock hook -> SensorChecker, per-channel last-good, DtcDebouncer. | Добавить never-seen/missed-window handling, реальные delays и fault->action. LimpLevel1/2 не считать готовыми ступенями мощности. |
| Таблица boost cut | Только master в проверенной паре<br>[F15](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L160) [S15](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/limp_manager.cpp) | LimpManager: boostCutUseTable/boostCutTable, selectable X/Y, telemetry. | Портировать table/axis lookup. Не переносить getOrZero + fixed hysteresis вместо validity/latch rusEFI. |
| Torque request allocation | Master development; torque_model.cpp в stable отсутствует<br>[F30](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13) [F22](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_reduction_controller.cpp#L16) [F49](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine.h#L193) | TorqueModel arbitration/ceilings, commandSparkReduction; TorqueReductionController::update. | Архитектурная идея, не drop-in: 90 Nm/(g air), TODO sources и soft limiter требуют замены/валидации. Добавить launch/ALS/shift/N2O/fault priorities. |
| Дополнительные идеи | Проверен master<br>[F12](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel_cell.cpp#L34) [F04](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine2.cpp#L105) [F25](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/idle_thread.cpp#L25) | Relative STFT error; ASE seconds; setDTermOverride(-rpmRate) для idle. | Только по выбранной семантике. STFT signs/gains/deadband и gating сохранить/перенастроить; rpmRate требует фильтрации. Они не закрывают каскад ХХ. |

### Что нельзя переносить целиком

**STFT:** у FOME и rusEFI разные формула ошибки, знаки maxRemove и набор gates; четыре banks не нужны при одной lambda. **Injector model:** FOME не заменяет 2D deadtime и DI pressure/mass rusEFI. **ALS:** ungated skip и поздний update требуют нового корректного path. **Boost cut:** table полезна, getOrZero не должен уничтожить rusEFI validity/latch. **TorqueControl:** подключённый код не равен законченной модели спортивного ECU. [R12](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel_cell.cpp#L9) [R13](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel.cpp#L102) [F12](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel_cell.cpp#L34) [F13](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel.cpp#L83) [R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) [F18](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) [R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L67) [F15](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L160) [F30](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13)

FOME TorqueModel действительно включён в engine modules, выдаёт reduction request; engine2 применяет retard, spark_logic потребляет limiter, ETB выбирает torque target при enableTorqueModel. Однако модель использует временное приближение 90 Nm/(g air), demand arbitration пока max(driver,idle), а комментарии оставляют другие источники на будущее. Это архитектурный образец master; не готовая калибровочная модель и не обязательная зависимость нашего mass-based fuel. [F49](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine.h#L193) [F30](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13) [F04](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine2.cpp#L105) [F18](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) [F20](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L290)

## Новая работа объединяет существующие механизмы

### Подача топлива требует единого контракта массы

Предлагаемый порядок: AirMass/FuelRequest -> общие температурные/STFT/цилиндровые поправки -> DI/PI allocator -> отдельная PI Film/DI wall-wetting -> injector characterization -> финальная проверка дозы/окна -> scheduler. Итерация allocator с Film и ограничениями допустима, но её баланс массы должен быть определён явно. High-pressure feed-forward получает назначенную DI-массу всех цилиндров. Это проектная схема, а не описание уже существующего готового пути.

### Запрос режима и реально разрешённое действие различаются

Новый coordinator хранит owner, lifetime, state и reason каждого запроса. Он согласует spark, fuel, air, boost, N2O и pumps через Ready/Active/Exit/Re-arm/Fault. Защитный предел имеет приоритет; истёкший запрос не действует. Outer loops получают фактически разрешённые значения для anti-windup. Общий arbiter не требует принимать приблизительную torque model FOME целиком.

### Защита должна описывать возврат так же точно, как срабатывание

Для каждого правила задаются enable, validity, порог/карта, delay, hysteresis, действие, latch и recovery. Критическое событие может сразу отключить систему. Lean-monitor, DTC и limit - разные роли; отсутствие достоверной lambda или turbo speed требует отдельной политики. Намеренный cut отключает обучение смеси, но не давление, EGT, turbo и driver safety.

### Сначала проверяем подачу и защиту, затем настраиваем режимы

**1. Аппаратный контракт, schema/API и baseline.** Зафиксировать мотор, MCU, рампы, драйверы и ресурсы 6DI/6PI/2HPFP/2DC. Воспроизводимая сборка, собственная typed schema/единицы/capabilities; клиент разрабатывать параллельно firmware.

**2. Раздельные injector groups и измеримая масса.** Сначала разделить конфигурацию/pressure/нелинейности, затем перенести Short Pulse Adder и Flex estimator. Определить FuelProperties, min-dose и доступную capacity; добавить event telemetry.

**3. Независимые события и два ТНВД.** Реализовать allocator, DI/PI окна и финальную защиту события, PI Film и требуемую target-volume модель. Канализировать HPFP и привязку к VVT; проверить HIL до нагрузочных режимов.

**4. Защиты, EWG и native peripheral control.** Добавить per-cylinder knock action, thermal/turbo supervisors, EWG fault, generic PWM-PID и выбранные CAN/SENT/LIN профили. Точечные FOME checks/axes встраивать с сохранением rusEFI latch/validity.

**5. Режимный coordinator и выходы.** Согласовать launch/ALS/FFS/shift/overrun/N2O и каскад ХХ. Проверить совместные входы, запреты, причины и восстановление до калибровки на моторе.

## Приёмка должна воспроизводить переходы и отказы

Это план будущих build/simulation/HIL/bench проверок, а не выполненные результаты. Для каждой реализованной части требуется ожидаемый результат на уровне выходного события и состояния, а не только совпадение числа в интерфейсе. Пороговые значения выбираются по конкретному двигателю и компонентам.

| Проверка | Сценарий | Критерий принятия |
| --- | --- | --- |
| A1. Сборка и схема | Baseline - штатной цепочкой; целевой board profile - с собственной typed schema/capabilities. Unit tests, Lua/LTFT off и сохранение обязательных модулей. | Firmware и свой клиент согласуют поля/типы/единицы/версию без TS/INI. Несовместимая калибровка отклоняется или мигрирует явно. Flash/RAM/время измерены. |
| A2. Масса и injector model | Sweep RPM/load/Flex/pressure/Vbat, min dose и нелинейность; cylinder trims, STFT, Film и stage fraction. | Сумма назначенной DI+PI соответствует запросу либо явному ограничению; нет двойного trim/deadtime. Запрос/доступность/назначение и причины saturation видимы. |
| A3. Scheduler / два ТНВД | Симуляция и HIL: 6 DI + 6 PI + 2 ТНВД при VVT sweep, смене RPM, cut и потере sync. Проверить драйверные токовые профили на стенде. | Независимые окна DI/PI соблюдены; DI feed-forward учитывает все цилиндры и только DI. Нет зависших/повторных выходов, борьбы насосов общей рампы или недопустимых событий после отмены. |
| A4. Flex / Film / STFT | Invalid до первого sample, E85 -> shutdown/refuel/restart, NaN backup, signal recovery; PI-fraction/DFCO/ALS/launch переходы. | Единая оценка состава, определённый fallback/derate, непрерывность восстановления; Film не применяется к общей DI+PI массе. STFT не учится по intentional skips и возвращается после transport delay. |
| A5. Режимы / N2O | ALS disabled/armed/active при ratio 0/nonzero; смена ratio на 0; hard cut 100%; общий clutch FFS/launch; gear-confirm timeout; DFCO ramp !=0.5 s. | За пределами активного режима нет его остаточного запроса. Реальный hard cut полный; N2O снимается до/при запрете нужного топлива. Exit/Re-arm/Fault детерминированы, восстановление не возвращает накопленный PID. |
| A6. Boost / EWG / turbo | Ограниченная target меняется независимо от MAP; EWG invalid command/feedback, saturation и потеря привода; turbo pulses disappear/overspeed. | FF использует текущую ограниченную цель; outer PID учитывает inner limit. Turbo safety работает на полном SensorResult; units/range совпадают в логах. Safe behavior подтверждён для фактической механики. |
| A7. Fault injection | Invalid MAP после overboost, EGT fault во время ALS, lambda invalid/rich, oil sensor fault при PWM, low/high fuel pressure, never-seen knock, saturation и missed windows. | Каждая защита имеет ожидаемые latch/action/recovery; invalid MAP не снимает активную защиту. Knock action адресуется нужному цилиндру, EGT/turbo/oil не отключаются вместе со STFT. |
| A8. Связь / нагрузка / питание | Одновременная работа 2 CAN/SENT/Flex/turbo; bus-off/timeout, LIN faults выбранных устройств, максимальный logging, питание/reset/watchdog. | Критические данные истекают по timeout; диагностика не блокирует scheduler. Записаны worst-case latency/missed events, состояние выходов при reset и доступность event history. |

## Аппаратные решения остаются открытыми

До схемы выводов остаются открыты точный двигатель, порядок работы и MCU; общая или раздельные DI-рампы; типы форсунок, ТНВД, peak-and-hold микросхем и их microcode; число VVT; механика EWG, измерение тока и turbo sensor; сухой/мокрый нитрос, число ступеней и силовые выходы; конкретные CAN/LIN/SENT устройства и электрические диапазоны всех датчиков. LIN - рабочая трактовка исходного «LINT». Это влияет на назначение ресурсов, фазирование и fault behavior, поэтому не может быть заменено выбором fork.

Проверка остаётся статической: сборки прошивок, запуск клиентов, bench/HIL, pinmux/DMA, токовые профили и нагрузка MCU не проверялись. Числа со скриншотов не являются рекомендациями для двигателя; скрытые формулы чужого ECU не восстановлены. Проценты готовности, экономии ресурсов и сроки без реализации и измерений не приводятся.

### Скриншоты задают настройки, но не раскрывают алгоритм

Полное соответствие включает не только основные карты, но и единицы, validity, limits, rate limits, enable conditions и наблюдаемое состояние. Для Fuel Film надо отдельно определить Efficiency load, источник lambda/добавочного канала, reset физического состояния и ограничение отрицательной массы. Для ХХ - смысл armed override, afterstart offset, скорость ramp, angle reserve и преобразование air flow % в DBW. Для knock - ВМТ окна, time constant и смысл Ignition cut delay. Для boost - reference pressure, filtered/predicted pressure и явное различие request correction и safety ceiling. Эти решения являются реализацией ТЗ; математическая эквивалентность чужому ECU не заявляется.

### Дополнительные функции не подменяют обязательные

Pit-speed, Track/Drift/Wet, traction control и ручник остаются предложениями ассистента, отдельно от обязательных функций ECU и клиента. Необходимые физические входы уточняются по выбранным устройствам. AC load input допустим без обязательного управления компрессором; CO2 bottle control не входит в EWG комплектацию.

### Собственный удобный клиент обязателен

Прямое требование пользователя: целевой продукт имеет полностью собственный клиент и не зависит от TunerStudio или INI. Нужны своя версионируемая typed schema параметров/карт/каналов, native protocol/API/capabilities, 2D/3D-редакторы, offline/online проекты и калибровки с diff/undo/save/migration, live telemetry/graphs/logging и log viewer, диагностика/trigger/service, firmware update/recovery. Стек пока не выбран. UX проверяется на реальных задачах настройки; клиент - обязательное направление параллельно firmware, не замена ECU-функциям.

У rusEFI уже есть собственный tuner, protocol read/write, редактор карт и log viewer. Эти открытые компоненты можно адаптировать, заменив INI-связь config/table metadata нашей схемой; базовый log viewer допускает работу без INI. Генератор FOME также даёт основу layout, а не готовую новую schema. FOME документирует TunerStudio + INI и служебную Console; полный самостоятельный клиент по нашему ТЗ не подтверждён. Приёмка: round-trip калибровки, миграции, разрыв связи при записи, live/log и update/recovery без TS/INI. Это собственный продукт, но не требование заново писать все компоненты. [R51](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/readme.md#L1) [R52](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288) [R53](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292) [R54](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java#L189) [F55](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java) [U01](https://github.com/FOME-Tech/fome-fw/blob/master/firmware/tunerstudio/readme.md) [U02](https://wiki.fome.tech/Intro-Start-Here/HT-Updating-The-Firmware/) [U03](https://github.com/FOME-Tech/fome-fw#what-do-we-have-here)

### Результат аудита меняет точку принятия решения

Первый критерий успеха firmware - корректное выходное событие при совместных ограничениях подачи, фаз и защиты. Для собственного клиента такой критерий - понятное и проверяемое управление тем же контрактом. Переиспользование открытых компонентов оценивается по этим двум результатам.

## Индекс доказательств: ссылки ведут на фиксированный код

R = rusEFI 5a42c8b3; F = FOME master 9f45bdee; S = FOME stable 343fb818. Полные SHA приведены в начале. Ссылки открывают исходный файл на указанной строке; соседние функции этого файла могут быть разобраны в той же строке матрицы. Индекс предназначен для review и воспроизведения статического аудита.

**01. Масса воздуха / Speed Density**
firmware/controllers/algo/airmass/speed_density_base.cpp
[R01](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/airmass/speed_density_base.cpp#L26) L26

**02. Масса топлива, stoich и Flex fallback**
firmware/controllers/algo/fuel/fuel_computer.cpp
[R02](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/fuel_computer.cpp#L22) L22; [F02](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.cpp#L12) L12; [S02](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/fuel_computer.cpp#L50) L50

**03. Температура заряда**
firmware/controllers/math/speed_density.cpp
[R03](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/speed_density.cpp#L24) L24

**04. Поцилиндровые массы, trims и угол**
firmware/controllers/algo/engine2.cpp
[R04](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/engine2.cpp#L98) L98; [F04](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine2.cpp#L105) L105

**05. Пуск, температурные коррекции, staging, duty**
firmware/controllers/algo/fuel_math.cpp
[R05](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel_math.cpp#L42) L42; [F05](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel_math.cpp#L339) L339

**06. Вход Flex Fuel**
firmware/controllers/sensors/flex_sensor.cpp
[R06](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/flex_sensor.cpp#L8) L8

**07. Начальная загрузка Flex filter**
firmware/init/sensor/init_flex.cpp
[F07](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/init/sensor/init_flex.cpp#L57) L57

**08. Модель форсунки, deadtime, short pulse**
firmware/controllers/algo/fuel/injector_model.cpp
[R08](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/injector_model.cpp#L31) L31; [F08](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/injector_model.cpp#L62) L62; [S08](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/algo/fuel/injector_model.cpp#L197) L197

**09. Константа плотности топлива**
firmware/controllers/algo/fuel/fuel_computer.h
[R09](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/fuel_computer.h#L39) L39; [F09](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/fuel_computer.h#L51) L51

**10. Film, разделение дозы и начало событий**
R: firmware/controllers/engine_cycle/main_trigger_callback.cpp
F: firmware/controllers/engine_cycle/fuel_schedule.cpp
[R10](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/main_trigger_callback.cpp#L64) L64; [F10](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/fuel_schedule.cpp#L92) L92

**11. ТНВД: расход, фаза и выход**
firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp
[R11](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L61) L61; [F11](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/high_pressure_fuel_pump.cpp#L73) L73

**12. STFT: ошибка и пределы**
firmware/controllers/math/closed_loop_fuel_cell.cpp
[R12](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel_cell.cpp#L9) L9; [F12](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel_cell.cpp#L34) L34

**13. STFT: разрешения и блокировки**
firmware/controllers/math/closed_loop_fuel.cpp
[R13](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/closed_loop_fuel.cpp#L102) L102; [F13](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/closed_loop_fuel.cpp#L83) L83

**14. Модель топливной плёнки**
firmware/controllers/algo/wall_fuel.cpp
[R14](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/wall_fuel.cpp#L15) L15; [F14](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/wall_fuel.cpp#L14) L14

**15. LimpManager: масло, overboost, duty, cut**
firmware/controllers/limp_manager.cpp
[R15](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/limp_manager.cpp#L67) L67; [F15](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/limp_manager.cpp#L160) L160; [S15](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/limp_manager.cpp) файл целиком

**16. Launch и SoftSparkLimiter**
firmware/controllers/algo/launch_control.cpp
[R16](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/launch_control.cpp#L73) L73; [F16](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/launch_control.cpp#L81) L81

**17. ALS: условия и время**
firmware/controllers/algo/antilag_system.cpp
[R17](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/antilag_system.cpp#L38) L38; [F17](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/antilag_system.cpp#L60) L60

**18. Исполнительный ALS spark-skip**
firmware/controllers/engine_cycle/spark_logic.cpp
[R18](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/spark_logic.cpp#L676) L676; [F18](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/spark_logic.cpp#L429) L429; [S18](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/engine_cycle/spark_logic.cpp#L443) L443

**19. Угол, CLT/IAT, поцилиндровые карты**
firmware/controllers/algo/ignition/ignition_state.cpp
[R19](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/ignition/ignition_state.cpp#L91) L91; [F19](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/ignition/ignition_state.cpp#L110) L110

**20. DBW/EWG: каскад и проверка output**
firmware/controllers/actuators/electronic_throttle.cpp
[R20](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/electronic_throttle.cpp#L258) L258; [F20](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/electronic_throttle.cpp#L290) L290

**21. FFS / ShiftTorqueReductionController**
firmware/controllers/algo/shift_torque_reduction_controller.cpp
[R21](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/shift_torque_reduction_controller.cpp#L17) L17

**22. Распределение retard и spark cut**
firmware/controllers/algo/torque/torque_reduction_controller.cpp
[F22](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_reduction_controller.cpp#L16) L16

**23. Контекст двигателя и переключения**
firmware/controllers/modules/engine_state_machine/engine_state_machine.cpp
[R23](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/modules/engine_state_machine/engine_state_machine.cpp#L122) L122

**24. DFCO и восстановление угла**
firmware/controllers/algo/fuel/dfco.cpp
[R24](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/fuel/dfco.cpp#L9) L9; [F24](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/fuel/dfco.cpp#L9) L9

**25. Холостой ход, воздух и угол**
firmware/controllers/actuators/idle_thread.cpp
[R25](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/idle_thread.cpp#L37) L37; [F25](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/idle_thread.cpp#L25) L25

**26. VVT, feed-forward и ramp**
firmware/controllers/actuators/vvt.cpp
[R26](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/vvt.cpp#L87) L87; [F26](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/vvt.cpp#L85) L85; [S26](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/vvt.cpp#L133) L133

**27. Boost target, оси и feed-forward**
firmware/controllers/actuators/boost_control.cpp
[R27](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/boost_control.cpp#L79) L79; [F27](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/boost_control.cpp#L47) L47; [S27](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/actuators/boost_control.cpp#L47) L47

**28. Доступные источники осей**
R: firmware/controllers/actuators/gppwm_channel_reader.cpp
F: firmware/controllers/actuators/gppwm/gppwm_channel.cpp
[R28](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm_channel_reader.cpp#L9) L9; [F28](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L10) L10

**29. Нитрос и запрет впрыска**
firmware/controllers/algo/nitrous_controller.cpp
[R29](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/algo/nitrous_controller.cpp#L11) L11

**30. TorqueModel: запросы, ограничения, модель**
firmware/controllers/algo/torque/torque_model.cpp
[F30](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/torque/torque_model.cpp#L13) L13

**31. Knock: измерения и общий retard**
firmware/controllers/engine_cycle/knock_controller.cpp
[R31](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/engine_cycle/knock_controller.cpp#L19) L19; [F31](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/engine_cycle/knock_controller.cpp#L43) L43

**32. Software knock DSP и доступность ADC**
firmware/controllers/sensors/impl/software_knock.cpp
[R32](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/impl/software_knock.cpp#L73) L73

**33. Пример двух физических knock-входов**
firmware/config/boards/proteus/knock_config.h
[R33](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/proteus/knock_config.h#L8) L8

**34. SensorChecker, DTC, knock low-noise**
firmware/controllers/sensors/sensor_checker.cpp
[R34](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/sensor_checker.cpp#L169) L169; [F34](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/sensor_checker.cpp#L261) L261; [S34](https://github.com/FOME-Tech/fome-fw/blob/343fb818014f082a14dc7dd25e69c29cfbd5bafb/firmware/controllers/sensors/sensor_checker.cpp#L553) L553

**35. Lambda monitor**
firmware/controllers/math/lambda_monitor.cpp
[R35](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/math/lambda_monitor.cpp#L16) L16; [F35](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/math/lambda_monitor.cpp#L45) L45

**36. Регистрация EGT-датчиков**
firmware/init/sensor/init_egt.cpp
[R36](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/init/sensor/init_egt.cpp#L16) L16

**37. Преобразователь turbo frequency -> RPM**
firmware/controllers/sensors/converters/turbocharger_speed_converter.h
[R37](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/sensors/converters/turbocharger_speed_converter.h#L9) L9; [F37](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/sensors/converters/turbocharger_speed_converter.h#L8) L8

**38. Формат telemetry turboSpeed**
firmware/console/binary/output_channels.txt
[R38](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/console/binary/output_channels.txt#L221) L221; [F38](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/console/binary/output_channels.txt#L230) L230

**39. GPPWM: таблица, dutyIfError**
firmware/controllers/actuators/gppwm/gppwm_channel.cpp
[R39](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L49) L49; [F39](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/actuators/gppwm/gppwm_channel.cpp#L150) L150

**40. Две CAN: настройка и запуск**
firmware/hw_layer/drivers/can/can_hw.cpp
[R40](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/drivers/can/can_hw.cpp#L115) L115; [F40](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/hw_layer/drivers/can/can_hw.cpp#L63) L63

**41. SENT decoder**
firmware/hw_layer/drivers/sent/sent.cpp
[R41](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/drivers/sent/sent.cpp#L83) L83

**42. K-line не равен прикладному LIN**
firmware/hw_layer/kline.cpp
[R42](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/kline.cpp#L1) L1

**43. Power4GDI: pins и число DC outputs**
firmware/config/boards/hellen/alphax-4K-GDI/board_configuration.cpp
[R43](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/hellen/alphax-4K-GDI/board_configuration.cpp#L20) L20

**44. Feature guards и генерация страниц**
docs/firmware-flash-usage.md
[R44](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/docs/firmware-flash-usage.md#L169) L169

**45. DTC freeze-frame и tooth history**
firmware/controllers/modules/dtc_manager/dtc_manager.cpp
[R45](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/modules/dtc_manager/dtc_manager.cpp#L122) L122

**46. CRC, версия, размер и резервная копия**
firmware/controllers/flash_main.cpp
[R46](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/controllers/flash_main.cpp#L143) L143

**47. Watchdog API**
firmware/hw_layer/ports/mpu_watchdog.h
[R47](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/hw_layer/ports/mpu_watchdog.h#L26) L26

**48. Сохранение Flex из рабочего callback**
firmware/controllers/algo/engine.cpp
[F48](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine.cpp#L94) L94

**49. Включение TorqueModel**
firmware/controllers/algo/engine.h
[F49](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/firmware/controllers/algo/engine.h#L193) L193

**50. SENT в конфигурации Power4GDI**
firmware/config/boards/hellen/alphax-4K-GDI/board.mk
[R50](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/firmware/config/boards/hellen/alphax-4K-GDI/board.mk#L8) L8

**51. Существующий собственный rusEFI tuner**
java_console/readme.md
[R51](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/readme.md#L1) L1

**52. Клиентский protocol и зависимость от INI**
java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java
[R52](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/io/src/main/java/com/rusefi/binaryprotocol/BinaryProtocol.java#L288) L288

**53. Редактор карт и его metadata contract**
java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java
[R53](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/widgets/tune/TuningTableView.java#L1292) L1292

**54. Просмотрщик логов и optional INI**
java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java
[R54](https://github.com/rusefi/rusefi/blob/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9/java_console/ui/src/main/java/com/rusefi/ui/logview/LogViewerPanel.java#L189) L189

**55. Генератор layout и клиентских описателей**
java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java
[F55](https://github.com/FOME-Tech/fome-fw/blob/9f45bdeeb59080a09f3fd7ca8568c7ef73372fb6/java_tools/configuration_definition/src/main/java/com/rusefi/ConfigDefinition.java) файл целиком

**C01. Изменение rusEFI HEAD во время аудита**
Только три PNG разъёмов между baseline и 4956c121. [C01](https://github.com/rusefi/rusefi/compare/5a42c8b3df0ab1540327c5648cb81ef1b58ab2a9...4956c1212ec8414450d699e6a74e0949f3a27c5e)

**U01-U03. Официальные материалы о программе настройки**
TunerStudio INI [U01](https://github.com/FOME-Tech/fome-fw/blob/master/firmware/tunerstudio/readme.md); процедура обновления [U02](https://wiki.fome.tech/Intro-Start-Here/HT-Updating-The-Firmware/); назначение Console [U03](https://github.com/FOME-Tech/fome-fw#what-do-we-have-here). Эти ссылки относятся к документации, просмотренной 25.10.2026, и не зафиксированы SHA.
