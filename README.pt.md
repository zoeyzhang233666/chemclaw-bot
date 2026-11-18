# ChemClaw v0.3.0

[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Русский](README.ru.md) | [Français](README.fr.md) | [العربية](README.ar.md) | [Español](README.es.md) | **Português**

**No comércio físico de produtos químicos, o que realmente importa é encontrar clientes com procura concreta, fornecedores capazes de entregar e preços com origem, data e condições de negociação verificáveis.**

- Vende carbonato de sódio denso? Localize fabricantes de vidro que estejam a instalar novas linhas de produção e que possam precisar de mais matéria-prima.
- Compra óxido de propileno? Separe produtores, agentes e distribuidores de stock imediato e compare os preços entregues.
- Importa monoetilenoglicol? Verifique as instalações dos produtores estrangeiros e calcule o custo total posto na fábrica.
- Analisa metanol? Cruze preços físicos, futuros, inventários e paragens de unidades numa base de investigação auditável.

O ChemClaw vem com duas ligações preparadas: **[Chemcloud Data Hub](https://mcp.chem-cloud.cn/)** para dados especializados da indústria química e **[APIHub](https://apihub.chem-cloud.cn/)** para acesso a modelos de IA a preços acessíveis. Basta obter as chaves e introduzi-las nas definições, sem programar integrações.

O conjunto de dados da Chemcloud, *High-Quality Industry-Specific Knowledge Dataset for Chemical Industry Agents*, foi selecionado como **caso de referência de conjuntos de dados setoriais de elevada qualidade de Xangai em 2026** e apresentado durante a **Global Data Ecosystem Conference 2026**. [Anúncio oficial](https://dt.sheitc.sh.gov.cn/cms/slddt/3123.jhtml). A distinção evidencia o trabalho com dados da indústria; para decisões comerciais é indispensável confirmar os documentos de origem.

O ChemClaw integra **50 agentes especializados, 15 grupos de colaboração e 108 competências para o setor químico**. Abrange vendas e compras nacionais e internacionais, fundamentos de energia e produtos químicos, análise de spot e futuros e investigação quantitativa. Os resultados podem ser gráficos na conversa, Excel, PowerPoint, Word e páginas web interativas.

## Índice

1. [Porquê ChemClaw em vez de IA generalista?](#1-porquê-chemclaw-em-vez-de-ia-generalista)
2. [Fontes de dados e oportunidades comerciais](#2-fontes-de-dados-e-oportunidades-comerciais)
3. [Comércio físico nacional](#3-comércio-físico-nacional)
4. [Comércio internacional de químicos](#4-comércio-internacional-de-químicos)
5. [Energia, futuros e análise quantitativa](#5-energia-futuros-e-análise-quantitativa)
6. [Gráficos diretamente na conversa](#6-gráficos-diretamente-na-conversa)
7. [Relatórios e ficheiros de entrega](#7-relatórios-e-ficheiros-de-entrega)
8. [Alterar ficheiros Office existentes](#8-alterar-ficheiros-office-existentes)
9. [Navegador e decisões do utilizador](#9-navegador-e-decisões-do-utilizador)
10. [Agentes e grupos de trabalho](#10-agentes-e-grupos-de-trabalho)
11. [Instalação e configuração](#11-instalação-e-configuração)
12. [Exemplos práticos de pedidos](#12-exemplos-práticos-de-pedidos)

---

## 1. Porquê ChemClaw em vez de IA generalista?

Uma IA genérica consegue pesquisar e escrever relatórios. A vantagem do ChemClaw é ter **dados de química, métodos de verificação, processos comerciais e papéis profissionais já organizados**, evitando que cada equipa tenha de configurar tudo de raiz.

| Necessidade | IA generalista | ChemClaw |
| --- | --- | --- |
| **Encontrar quem utiliza a matéria-prima** | Lista empresas, mas o consumo exige validação | Data Hub para aplicações e empresas; EIA, listas de matérias-primas, fábricas e expansões como provas |
| **Escolher um fornecedor real** | Sugere potenciais fornecedores | Distingue produtores e distribuidores, verifica instalações, grades, licenças e documentação; aponta stock, COA e prazos a confirmar |
| **Comparar preços spot** | Datas, mercados e condições podem variar | Dá prioridade a cotações físicas com região, qualidade, data, imposto e base de entrega; não confunde futuros com spot |
| **Encontrar novos negócios** | Notícias e resultados de pesquisa | Cruza projetos industriais, documentos governamentais, concursos e PDF originais CNINFO para gerar ações comerciais |
| **Importar e exportar** | Pesquisa e tradução | Verifica produtores, compradores e custos FOB/CFR/CIF, taxas, divisa e logística |
| **Investigar futuros e padrões** | Explica conceitos estatísticos | Base, spreads de vencimentos, sazonalidade, inventários, lead–lag, eventos e backtests com contratos negociáveis |
| **Entregar resultados à equipa** | Texto e ficheiros separados | Colaboração multiagente, gráficos no chat e Excel, PPT, Word e páginas web com fontes |

## 2. Fontes de dados e oportunidades comerciais

### 2.1 Chemcloud Data Hub: dados para comércio de químicos

[Peça uma chave de dados](https://mcp.chem-cloud.cn/) e introduza-a em **Definições → Conectores → Chemcloud Data Hub**. O endereço já está configurado; o acesso aos registos depende das permissões da conta.

| Categoria | Informação disponível conforme autorização | Utilização |
| --- | --- | --- |
| **Compostos químicos** | CAS, nomes, perfis de substâncias, MSDS/SDS, produtos e preços acessíveis | Confirmar a substância e evitar confusões de nomes, composição ou classe comercial |
| **Empresas e clientes** | Pesquisa empresarial, registo, acionistas, grupo societário, patentes, concursos, ficha cliente 360° | Identificar compradores, fábricas, filiais, produtores e projetos |
| **Transações e encomendas** | Consultas, propostas, ordens de compra/venda, movimentos de stock, resumos de recebimentos | Analisar **apenas os dados internos autorizados** sobre encomendas, existências e cobranças |
| **Mercados e preços** | Informação de mercados e tendências/históricos disponíveis | Comparar preços físicos pela data, região, especificação e condições de entrega |

> Vendemos óxido de propileno nas regiões chinesas de Jiangsu e Zhejiang. Começa por Chemcloud Data Hub para identificar produtores de polióis poliéter e propilenoglicol, verifica as instalações nos respetivos sites, EIA e anúncios de expansão. Entrega Excel com fábrica, prova de consumo, fonte, grau de confiança e prioridade comercial. Não inventes consumos anuais.

### 2.2 Projetos, licenciamento e estudos ambientais

**Relatórios de impacto ambiental (EIA)**, autorizações de emissões, documentação de projetos, comunicados de parques industriais e outras fontes governamentais podem indicar **localização da fábrica, equipamento, capacidade prevista e consumo anual de matérias-primas**. Distinguir aprovação, construção, arranque experimental e produção comercial; a capacidade de projeto não é disponibilidade de entrega.

### 2.3 CNINFO: consulta integrada de PDF oficiais

O ChemClaw pesquisa divulgações de empresas chinesas cotadas em A-shares na [CNINFO](https://www.cninfo.com.cn/) por nome, código, palavra-chave e período. Pode obter o **PDF original** e extrair trechos legíveis identificando a página. Não exige uma chave CNINFO separada.

| Documento | Informações a procurar | Para que serve |
| --- | --- | --- |
| **Relatórios anuais/semestrais** | Produtos, fábricas, vendas, investimentos e obras em curso | Confirmar a escala e a atividade da empresa |
| **Investimentos, expansões e modernizações** | Projeto, instalação, montante, produto, capacidade prevista, calendário | Antecipar procura adicional ou novas fontes de oferta |
| **Ensaios, arranques e paragens** | Progresso e estado publicado da unidade | Separar anúncios de produção efetiva |
| **Contratos relevantes, prospetos e respostas regulatórias** | Partes, equipamentos, processos, estrutura de fornecimento | Investigar relações comerciais e validar valores |

PDF digitalizados ou com tipos de letra incompatíveis podem não fornecer texto fidedigno; confirme números e tabelas no original.

### 2.4 Concursos, fornecedores e preços físicos

Procure avisos acessíveis na [plataforma chinesa de recursos públicos](https://www.ggzy.gov.cn/), sistemas de compras de grandes empresas de química e energia, páginas de compras de fabricantes e parques industriais. Registe **entidade, produto, especificações, quantidade, destino, prazo, ligação e estado aberto/fechado/adjudicado**.

Para spot, comece pelo Data Hub e confirme com conteúdo público disponível de **Longzhong, SCI99/Zhuochuang, Jinlianchuang, Baichuan, Mysteel, SunSirs e SMM**. Alguns históricos e relatórios exigem subscrição. Não misture preço de tabela, referência de mercado e preço de negócio fechado.

### 2.5 Bolsas, bases de química e comércio externo

- **AKShare**: históricos OHLC efetivamente disponíveis de certos futuros e ações; velas apenas com abertura, máximo, mínimo e fecho reais; sem garantia de preços em tempo real.
- **Bolsas e páginas de finanças**: DCE, CZCE, SHFE, INE, GFEX e conteúdo público da Sina Finance, Eastmoney e Tencent Finance; a pesquisa não representa API exclusiva para todos os serviços.
- **[PubChem](https://pubchem.ncbi.nlm.nih.gov/), [OPSIN](https://opsin.ch.cam.ac.uk/), Wikipédia, Huagongshe**: nomes, fórmulas e identidade química; as especificações e qualidade de lotes exigem SDS/TDS/COA.
- **UN Comtrade, WITS e alfândegas**: comércio por país e códigos de produtos; números nacionais não comprovam compras de uma empresa específica.

### 2.6 Sites estrangeiros, LinkedIn e X

Sites de produtores, exposições, diretórios Kompass, Thomasnet, Europages, EC21, Indotrading, IndiaMART, páginas empresariais públicas do **LinkedIn** e publicações públicas no **X** podem ajudar a identificar produtos, fábricas, contactos institucionais e projetos. É pesquisa de conteúdo público, **não acesso garantido a APIs privadas ou recolha integral de redes sociais**. Algumas plataformas exigem ligação internacional/proxy e credenciais do utilizador; login, CAPTCHA e pagamentos ficam a cargo deste.

## 3. Comércio físico nacional

**Vendas:** seguir o produto até aos processos e fábricas utilizadoras; verificar consumos nos estudos ambientais e projetos. **Compras:** separar produtor, empresa de vendas do fabricante, agente autorizado e distribuidor de stock; solicitar documentação técnica, qualidade, disponibilidade, proposta de preço, prazo e condições financeiras.

> Pretendo comprar 300 toneladas de dióxido de titânio rutilo com entrega em Wuhu. Usa Chemcloud Data Hub e competências de verificação de fabricantes para criar listas separadas de produtores, agentes e distribuidores. Valida fábricas, fichas técnicas e licenças. Entrega uma RFQ Excel com preço com impostos e entrega, embalagem, COA, stock, prazo e condições de pagamento por confirmar; não deduzas capacidade industrial apenas do registo da sociedade.

## 4. Comércio internacional de químicos

As competências de exportação cobrem **seleção de países, compradores industriais, importadores, distribuidores, verificação de consultas recebidas, propostas, faturas pró-forma e documentação**. Na importação, confirmam produtores, instalações, produtos, capacidades anunciadas e condições de operação, e calculam custos de FOB/CFR/CIF, câmbio, imposto, IVA, porto, seguro e transporte interior.

> Exportamos TiO2 rutilo para a Índia e a Indonésia. Pesquisa fabricantes de tintas e plásticos, importadores e distribuidores usando dados de comércio por país, sites de fábricas, registos locais, feiras, associações e páginas LinkedIn públicas. Entrega Excel com provas verificáveis, contactos corporativos públicos, segmentação dos candidatos e e-mail inicial em inglês. Nunca atribuas o volume importado pelo país a uma empresa específica.

> Para importar MEG da Arábia Saudita e dos Emirados, verifica fabricantes reais, unidades de produção, capacidade de projeto, operação publicada e canais de venda, distinguindo MEG de DEG. Cria uma tabela Excel de custo posto em fábrica com FOB/CFR/CIF, câmbio, taxas e transporte parametrizáveis e um e-mail RFQ em inglês.

## 5. Energia, futuros e análise quantitativa

Pesquise petróleo, GPL, metanol, carbonato de sódio, PVC, glicóis e outros mercados através de **preços spot e futuros, base, spreads entre vencimentos, inventários, taxas de operação, manutenção, novas capacidades, margens e política comercial**. Inclui sazonalidade, correlação, relações lead–lag, estudos de eventos e backtests de regras expressas.

| Estudo | Disciplina necessária | Entregável |
| --- | --- | --- |
| **Base spot–futuros** | Recolher séries separadas, alinhar datas/unidades, identificar o contrato | Duas séries de preços e curva de base, Excel |
| **Spreads e fundamentos** | Vencimento, rolagem, regiões, inventários, paragens e investimentos | Gráficos, calendário e análise com fontes |
| **Estatística e lead–lag** | Data efetiva da divulgação, tamanho de amostra, correção para testes múltiplos | Distribuição de defasagens, valores p/q, estabilidade por ano |
| **Backtest** | Contratos realmente negociáveis, custos, rolagens, avaliação fora da amostra | Resultado histórico reproduzível e sensibilidade, sem promessa futura |

> Analisa a base entre o metanol físico de Taicang e os futuros MA no último trimestre. Usa primeiro Chemcloud Data Hub e cotações físicas públicas para spot; `chem_futures_history` e dados da bolsa para os futuros. Alinha datas e unidades, mostra linhas de preços e curva de base separada, cria Excel de dados/fórmulas/fontes e um PPT de 4 a 6 slides. Nunca substituas observações spot em falta por futuros.

> Verifica se a variação do stock portuário de metanol antecipa rendimentos dos futuros MA nas 1–8 semanas seguintes. Considera o momento real de publicação, todas as defasagens, amostras, p/q corrigidos, estabilidade anual e avaliação fora da amostra. Entrega Excel reproduzível e relatório web interativo. Correlação não prova causalidade.

## 6. Gráficos diretamente na conversa

Quando existem dados reais, ChemClaw pode mostrar **linhas de preço spot, velas OHLC, comparação spot–futuros, base, cartões de indicadores, dispersão, heatmaps, radar, treemap, Sankey e cronologias**. Não produz uma série ou velas fictícias para preencher lacunas.

## 7. Relatórios e ficheiros de entrega

| Formato | Utilização |
| --- | --- |
| **Excel** | Clientes, fornecedores, RFQ, preços, base, inventários, pedidos |
| **PowerPoint** | Relatórios de gestão, propostas, estudos e gráficos |
| **Word** | Documentos editáveis, notas comerciais e análises de contratos |
| **Web interativa** | Mapas, cronologias de projetos, filtros e painéis de mercado |

## 8. Alterar ficheiros Office existentes

O ChemClaw consegue inspecionar ficheiros Word/PPT/Excel e efetuar alterações suportadas: edições localizadas e comentários no Word, ordem de slides, verificação de tabelas e fórmulas. Confirme o aspeto final e os cálculos complexos no software Office adequado.

## 9. Navegador e decisões do utilizador

Cada Bot no ambiente de trabalho pode abrir sites, ler páginas, clicar, preencher campos e resumir fontes acessíveis. **Login, pagamentos e CAPTCHA são efetuados pelo utilizador**; publicações, carregamentos ou eliminações podem exigir aprovação. Sites externos requerem ligação de rede adequada e, em certos casos, proxy.

## 10. Agentes e grupos de trabalho

São **50 Bots e 15 grupos** para vendas, compras, exportação, importação, investigação setorial, spot–futuros, quant, documentos e validação de evidências. O coordenador distribui funções e pode chamar-se um especialista com `@`.

## 11. Instalação e configuração

1. Descarregue **ChemClaw v0.3.0** para Windows, macOS Intel/Apple Silicon ou Linux nas [GitHub Releases](https://github.com/zoeyzhang233666/chemclaw-bot/releases).
2. Obtenha a chave do modelo no [APIHub](https://apihub.chem-cloud.cn/) e introduza-a em **Definições → Modelos → APIHub**. Confirme os preços, prazos e limites atuais no site.
3. Obtenha uma **chave de dados separada** no [Chemcloud Data Hub](https://mcp.chem-cloud.cn/) e introduza-a em **Definições → Conectores**.
4. Abra um especialista ou grupo e descreva a necessidade em linguagem natural.

Também é possível instalar o [plugin ChemClaw no DeepSeek Harness](https://github.com/zoeyzhang233666/chemclaw-bot/tree/main/chemclaw-bot).

## 12. Exemplos práticos de pedidos

**Novos clientes:**

> Vendemos carbonato de sódio denso no leste da China. Usa Chemcloud Data Hub para identificar fabricantes de vidro, depois verifica novas linhas, tabelas de matérias-primas em EIA, PDFs CNINFO e concursos abertos. Cria Excel por fábrica com fase do projeto, evidência de consumo, fonte, data, prioridade e próximo passo; apresenta uma cronologia no chat.

**Oportunidades de compra:**

> Procura nos últimos 30 dias concursos públicos ainda abertos para soda cáustica industrial destinada a alumina, papel ou tratamento de água. Verifica os avisos originais, separa concursos abertos de adjudicados, inclui concentração, quantidade, entrega, prazo e URL. Organiza uma lista Excel para acompanhamento.

---

## Antes de utilizar

ChemClaw é uma ferramenta de **investigação e apoio à decisão**, não executa ordens automáticas de futuros nem controla equipamentos industriais. Contratos, qualidade, conformidade e importações/exportações exigem verificação nas fontes originais. Utilize apenas dados e sites com acesso permitido. Licença **Apache-2.0**, baseada em **DS Bot e DeepSeek Harness**; consulte `NOTICE`.
