# 09 · Реестр доказательств

Каждый факт в продукте должен иметь строку здесь или поле `evidence` в данных.
Тип: **observed** — увидели сами на странице; **self-claim** — заявление компании о себе; **inferred** — наш вывод.

| ID | Факт | Источник | Дата (Asia/Almaty) | Тип |
|---|---|---|---|---|
| E-001 | Центр Красок №1: Алматы, ул. Кабдолова 1/8, блок 1, бутики 14 и 21; Астана, ул. Мангилик Ел 29/2; 10:00–20:00 | https://centr-krasok.kz/about/contacts/ | 2026-11-20 13:17 | observed |
| E-002 | Центр Красок №1: юрлицо ТОО «ЭКСПОНЕНТА1» | футер https://centr-krasok.kz/ | 2026-11-20 13:12 | observed |
| E-003 | Центр Красок №1: остатки товаров показываются по городам Алматы / Астана | https://centr-krasok.kz/catalog/dlya_detskoy/ | 2026-11-20 13:17 | observed |
| E-004 | Центр Красок №1: в каталоге Dulux, Luxium, Masterline, Hammerite, Oikos, Dufa | URL каталога на главной | 2026-11-20 13:12 | observed |
| E-005 | Центр Красок №1: главная без H1 и canonical; JSON-LD только WebSite | HTML главной | 2026-11-20 13:12 | observed |
| E-006 | Центр Красок №1: Караганды нет в адресах и на странице доставки | /about/contacts/, /about/delivery/ | 2026-11-20 13:17 | observed |
| E-007 | SVET.KZ: Алматы — ул. Кабдолова 1/8 (ТК Armada), пр. Жибек Жолы 135/10а; Астана — ул. Мангилик Ел 29/2 | https://svet.kz/contact/ | 2026-11-20 13:17 | observed |
| E-008 | SVET.KZ: «официальный дилер Maytoni», «35 000+ товаров» | meta description https://svet.kz/ | 2026-11-20 13:12 | self-claim |
| E-009 | SVET.KZ: отправка в Караганду транспортной компанией, от 1 дня | https://svet.kz/katalog/lyustry/ | 2026-11-20 13:17 | self-claim |
| E-010 | SVET.KZ: JSON-LD Organization с sameAs (Instagram, Facebook, YouTube, Google Maps) | HTML главной | 2026-11-20 13:12 | observed |
| E-011 | SVET.KZ: robots.txt содержит явный блок для OAI-SearchBot, ChatGPT-User, GPTBot, Claude-*, PerplexityBot, Google-Extended — закрыты только служебные /bitrix/, /local/ | https://svet.kz/robots.txt | 2026-11-20 13:11 | observed |
| E-012 | Оба магазина: телефон +7 (777) 292-84-01, адреса в одном ТК; e-mail SVET.KZ на домене abis.kz | контакты обоих сайтов | 2026-11-20 13:17 | observed; связь компаний — inferred |
| E-013 | Карточки 2ГИС SVET.KZ: 70000001043802009, 70000001043802177 (Алматы), 70000001090884645 (Астана) | ссылки с https://svet.kz/ | 2026-11-20 13:12 | observed (содержимое карточек не проверено) |
| E-014 | OLX.kz и e-katalog.kz отвечают 403 на автоматический запрос — исключены из корпуса | лог corpus.py | 2026-11-20 13:18 | observed |
| E-015 | Web-поиск «магазин красок Алматы» / «купить люстру Алматы» выдаёт в основном маркетплейсы (OLX, Satu, Kaspi объявления, e-katalog), клиентов в выдаче нет | WebSearch, 1 запуск каждого | 2026-11-20 13:18 | observed, 1 замер — не вывод |

Реальных ответов AI-поисковиков пока **0**.
