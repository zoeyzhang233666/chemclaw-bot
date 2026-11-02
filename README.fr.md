# ChemClaw v0.3.0

[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Русский](README.ru.md) | **Français** | [العربية](README.ar.md) | [Español](README.es.md) | [Português](README.pt.md)

**Dans le négoce de produits chimiques, l'essentiel est de trouver des clients ayant de réels besoins, des fournisseurs capables de livrer, et des prix au comptant dont la date, l'origine et les conditions sont vérifiables.**

- Vous vendez du carbonate de sodium dense ? Identifiez les verreries qui construisent de nouvelles lignes et pourraient avoir besoin de matière première.
- Vous achetez de l'oxyde de propylène ? Distinguez fabricants, agents commerciaux et distributeurs disposant de stock, puis comparez les coûts livrés.
- Vous importez du monoéthylène glycol ? Vérifiez les véritables sites de production et calculez un coût rendu usine.
- Vous analysez le méthanol ? Rassemblez prix physiques, futures, stocks et arrêts d'unités dans une étude traçable.

ChemClaw prévoit deux connexions utiles dès l'installation : **[Chemcloud Data Hub](https://mcp.chem-cloud.cn/)** pour les données sectorielles et **[APIHub](https://apihub.chem-cloud.cn/)** pour accéder à des modèles d'IA à tarif accessible. Il suffit d'obtenir les clés correspondantes et de les renseigner dans les paramètres de l'application.

Le jeu de données **« High-Quality Industry-Specific Knowledge Dataset for Chemical Industry Agents »** de Chemcloud a été sélectionné parmi les **cas de référence 2026 de Shanghai pour les jeux de données sectoriels de haute qualité**, présentés lors de la **Global Data Ecosystem Conference 2026**. [Annonce officielle](https://dt.sheitc.sh.gov.cn/cms/slddt/3123.jhtml). Cette reconnaissance renforce la crédibilité du travail sectoriel ; les décisions d'achat et de vente restent fondées sur la vérification des pièces originales.

ChemClaw inclut **50 agents spécialisés, 15 groupes de collaboration et 108 compétences métier** pour le commerce national et international, les fondamentaux des marchés énergétiques et chimiques, les contrats à terme et la recherche quantitative. Les résultats peuvent prendre la forme de graphiques dans le chat, de fichiers Excel, PowerPoint et Word ou de rapports web interactifs.

## Sommaire

1. [Pourquoi ChemClaw plutôt qu'un assistant généraliste ?](#1-pourquoi-chemclaw-plutôt-quun-assistant-généraliste-)
2. [Données et sources sectorielles](#2-données-et-sources-sectorielles)
3. [Vente et achat au comptant](#3-vente-et-achat-au-comptant)
4. [Commerce international](#4-commerce-international)
5. [Énergie, futures et recherche quantitative](#5-énergie-futures-et-recherche-quantitative)
6. [Graphiques dans la conversation](#6-graphiques-dans-la-conversation)
7. [Livrables et fichiers](#7-livrables-et-fichiers)
8. [Modification de documents Office](#8-modification-de-documents-office)
9. [Navigateur et contrôle humain](#9-navigateur-et-contrôle-humain)
10. [Agents et groupes](#10-agents-et-groupes)
11. [Installation et connexion](#11-installation-et-connexion)
12. [Exemples de demandes métier](#12-exemples-de-demandes-métier)

---

## 1. Pourquoi ChemClaw plutôt qu'un assistant généraliste ?

Les assistants généralistes peuvent rechercher sur Internet et produire des documents. ChemClaw se distingue par **des sources de données chimiques déjà prévues, des méthodes d'évaluation propres au négoce et des parcours métier prêts à l'emploi**.

| Votre question | Assistant IA généraliste | ChemClaw |
| --- | --- | --- |
| **Qui utilise réellement mon produit ?** | Liste d'entreprises à vérifier | Recherche de la chaîne aval dans Data Hub, puis contrôle des usines, des matières premières dans les études environnementales et des projets d'extension |
| **Qui peut réellement me fournir ?** | Fournisseurs potentiels | Fabricants et distributeurs séparés ; sites, grades, autorisations, COA, disponibilité et délais à confirmer |
| **Ce prix est-il comparable ?** | Chiffres venant de pages aux conventions variables | Priorité au marché physique ; date, zone, qualité, taxe, base de livraison et origine explicites ; pas de futures présentés comme spot |
| **Où naîtra la prochaine demande ?** | Articles et communiqués | Projets, permis, appels d'offres, PDF d'annonces boursières, calendrier industriel et plan de prospection |
| **Peut-on importer au bon coût ?** | Recherche et traduction | Vérification des producteurs, calcul FOB/CFR/CIF, taux de change, droits, TVA, fret et frais portuaires |
| **La relation entre stocks et prix est-elle fiable ?** | Explications statistiques | Base, spreads calendaires, saisonnalité, études d'événements, tests de décalage et backtests avec contrats négociables |
| **Que remettre à l'équipe ?** | Texte et fichiers isolés | Collaboration multi-agents, Excel traçable, présentations, documents modifiables et tableaux de bord |

## 2. Données et sources sectorielles

### 2.1 Chemcloud Data Hub : données utiles au négoce

[Obtenir une clé d'accès](https://mcp.chem-cloud.cn/) puis ouvrir **Paramètres → Connecteurs → Chemcloud Data Hub**. L'adresse du service est préconfigurée ; les données disponibles dépendent de vos droits.

| Catégorie | Contenu | Utilité pratique |
| --- | --- | --- |
| **Substances** | CAS, noms, fiches chimiques, MSDS/SDS, ressources documentaires et prix accessibles | Vérifier un produit dans une demande étrangère et éviter les confusions de composition ou de grade |
| **Entreprises et clients** | Recherche d'entreprises, immatriculation, actionnariat, organisations, brevets, appels d'offres, profil client 360° | Identifier usines, acheteurs, filiales et événements de marché |
| **Transactions et commandes** | Demandes de prix, devis, commandes d'achat/vente, mouvements de stocks, synthèses de paiements | Analyser uniquement les enregistrements d'entreprise **pour lesquels vous disposez d'une autorisation** |
| **Marchés et prix** | Marchés, points de vente et historiques/tendances accessibles | Comparer les cotations physiques à date, région, qualité et base de livraison constantes |

**Exemple :**

> Nous commercialisons de l'oxyde de propylène au Jiangsu et au Zhejiang. Utilise Chemcloud Data Hub pour identifier les produits aval, les fabricants de polyols polyéthers et de propylène glycol, puis vérifie leur usine dans les documents environnementaux et leurs sites. Fournis un Excel indiquant l'entreprise, le site, les preuves de consommation, la source, la fiabilité et le service à contacter ; n'invente pas les achats annuels.

### 2.2 Dossiers publics, permis et investissements

Les **études d'impact environnemental (EIA)**, permis d'émission, publications des autorités, zones chimiques et dossiers de projets peuvent révéler le lieu de production, le procédé, la capacité annoncée et parfois les **quantités annuelles de matières premières**. Une approbation administrative ne signifie pas que l'usine produit déjà : distinguer projet, construction, essais et mise en service.

### 2.3 CNINFO : recherche native dans les PDF officiels

ChemClaw possède un outil intégré pour rechercher les communications de sociétés cotées A-share sur [CNINFO](https://www.cninfo.com.cn/) par entreprise, code, mot-clé et période. Il peut récupérer le **PDF original** et des extraits lisibles avec leur page, sans clé CNINFO séparée.

| Type de document | Informations pertinentes | Décision aidée |
| --- | --- | --- |
| **Rapport annuel ou semestriel** | Produits, sites, ventes, immobilisations, constructions en cours | Identifier une activité industrielle réelle et son évolution |
| **Investissement, extension, modernisation** | Projet, usine, montant, capacité nominale, produit, calendrier | Anticiper nouveaux acheteurs et futures capacités d'approvisionnement |
| **Essais, démarrage ou arrêt d'unité** | Avancement, conditions opérationnelles publiées | Distinguer capacité annoncée et production disponible |
| **Contrat significatif, prospectus, réponse aux autorités** | Parties, contrat, procédés, fournisseurs/clients majeurs selon publication | Identifier liens commerciaux et vérifier des chiffres |

La lecture automatique d'un PDF peut être partielle, notamment pour les documents numérisés. Les chiffres et les pages doivent être revérifiés dans l'original.

### 2.4 Appels d'offres, fournisseurs et prix

ChemClaw peut rechercher les avis accessibles sur la [plateforme chinoise des marchés publics](https://www.ggzy.gov.cn/), les portails d'appels d'offres, les achats des grands groupes énergétiques et les sites des entreprises. Un avis **encore ouvert** doit être séparé d'un appel d'offres clôturé ou attribué. Les annuaires B2B servent à découvrir des candidats, pas à prouver une usine ou un stock réel.

Pour les prix physiques, la priorité va à Chemcloud Data Hub, complété selon le produit par des pages publiques de **Longzhong, SCI99/Zhuochuang, JLC, Baichuan, Mysteel, SunSirs, SMM**, et par les avis des fabricants. Séparer prix affiché, prix indicatif, prix négocié et rumeur ; certaines données nécessitent un abonnement.

### 2.5 Futures, marchés financiers et identité chimique

- **AKShare** : historiques OHLC accessibles pour certaines actions et certains futures ; graphiques en chandeliers lorsque de vraies données existent, sans garantie de cotations temps réel.
- **Bourses et pages de marché** : DCE, CZCE, SHFE, INE, GFEX, pages publiques de Sina Finance, Eastmoney et Tencent Finance ; recherche complémentaire, non pas accès API dédié à tous ces fournisseurs.
- **[PubChem](https://pubchem.ncbi.nlm.nih.gov/), [OPSIN](https://opsin.ch.cam.ac.uk/), Wikipédia, Huagongshe** : noms, structures, CAS et données chimiques de référence ; les spécifications commerciales demandent les SDS/TDS/COA du fabricant.
- **Statistiques commerciales** : UN Comtrade, WITS, données publiques de douanes et d'organisations professionnelles ; le volume importé par un pays n'est pas une commande prouvée d'une société.

### 2.6 Prospection internationale et réseaux professionnels

Sites de fabricants, registres étrangers, salons et annuaires (Kompass, Thomasnet, Europages, EC21, Indotrading, IndiaMART), pages LinkedIn d'entreprises et publications publiques sur X peuvent fournir des **indices commerciaux accessibles au public**. L'accès dépend du réseau, d'un éventuel proxy et des droits de connexion. ChemClaw ne revendique ni API officielle pour ces réseaux sociaux, ni accès aux contenus privés. Les connexions, paiements et CAPTCHA sont à effectuer par l'utilisateur.

## 3. Vente et achat au comptant

**Vente :** partir du produit et de ses débouchés, vérifier les véritables sites consommateurs, les études d'impact et les projets, puis classer les prospects selon la qualité de la preuve. **Achat :** séparer fabricant, filiale commerciale, distributeur autorisé et négociant de stock ; demander grade, COA, SDS, quantité réellement disponible, emballage, délai, modalités de paiement et prix rendu.

> Cherche des fabricants et distributeurs de dioxyde de titane rutile pour 300 tonnes livrées à Wuhu. Commence par Chemcloud Data Hub, puis vérifie sites, fiches techniques, licences et canaux de vente. Établis deux listes distinctes, un dossier de preuves et un tableau RFQ Excel avec prix TTC livré, disponibilité, COA, conditionnement et délais à confirmer. Aucun stock fictif.

## 4. Commerce international

Les compétences export/import traitent la **recherche de pays cibles, d'acheteurs finaux, d'importateurs, de distributeurs, de producteurs étrangers, de la vérification KYC, des devis et des documents de commerce international**. Pour l'import : modéliser devise, FOB/CFR/CIF, fret, assurance, douane, TVA, port et transport terrestre.

> Nous exportons du TiO2 rutile en Inde et en Indonésie. Utilise les données publiques UN Comtrade/WITS, les annuaires industriels, les sites d'usines, les registres locaux et les pages professionnelles publiquement accessibles. Distingue usines, importateurs et revendeurs. Livrables : base Excel bilingue avec sources et degrés de preuve, contacts professionnels publics, priorité commerciale et premier e-mail en anglais. Ne présente pas les volumes nationaux comme les achats d'une entreprise.

> Pour importer du MEG d'Arabie saoudite et des Émirats arabes unis, vérifie le producteur réel, l'usine, les grades, la capacité nominale et l'exploitation publiée. Fournis un e-mail RFQ en anglais et un Excel de coût rendu usine dont les hypothèses de fret, change et taxes restent modifiables.

## 5. Énergie, futures et recherche quantitative

ChemClaw couvre les fondamentaux des matières premières énergétiques et chimiques, la **base spot–futures, les spreads entre échéances, les écarts régionaux, la saisonnalité, les stocks et taux d'utilisation, les arrêts d'unités, la capacité nouvelle et les relations lead–lag**. Les compétences de recherche quantitative comprennent études d'événements et backtests de règles définies.

| Étude | Méthode indispensable | Résultat |
| --- | --- | --- |
| **Base physique–futures** | Séries physiques et futures distinctes, mêmes dates et unités ; contrat précisé | Deux courbes de prix + courbe de base, calcul Excel |
| **Spreads et fondamentaux** | Échéances, roulement, stocks, marges, arrêts et projets datés | Tableau des écarts, chronologie et commentaire sourcé |
| **Tests quantitatifs** | Temps réel de publication des données, taille d'échantillon, tests multiples, période hors échantillon | Rapport reproductible, sensibilités, graphiques et données |
| **Backtest** | Contrats effectivement cotés, coûts, roulements, dates de disponibilité | Résultats historiques sans promesse de gains futurs |

> Étudie les trois derniers mois de base entre méthanol physique à Taicang et futures MA. Prends d'abord le spot dans Chemcloud Data Hub, confronte-le aux informations publiques spécialisées ; récupère les OHLC des futures avec `chem_futures_history` et contrôle les règles de la bourse. Affiche les deux prix sur les mêmes dates et la base séparément, puis fournis Excel des données/sources et une présentation de 4 à 6 diapositives. Ne remplace jamais le spot manquant par des futures.

> Vérifie si les variations des stocks portuaires de méthanol précèdent les rendements de MA de 1 à 8 semaines. Utilise les vraies dates de publication, le test de tous les décalages, des valeurs p/q corrigées, les résultats par année et une évaluation de stabilité. Livrables : Excel reproductible et tableau de bord interactif. Corrélation n'implique pas causalité.

## 6. Graphiques dans la conversation

Selon les données réellement obtenues : courbes spot, chandeliers de futures, base, indicateurs, histogrammes, nuages de points, cartes thermiques, radars, treemaps, Sankey et chronologies. Un graphique en chandeliers nécessite des données **ouverture–plus haut–plus bas–clôture** authentiques.

## 7. Livrables et fichiers

| Fichier | Pour quoi faire |
| --- | --- |
| **Excel** | Listes de prospects, fournisseurs, appels d'offres, comparaisons de prix, calculs spot–futures, suivi des commandes |
| **PowerPoint** | Restitution commerciale, comité de direction, recherche de marché et graphiques |
| **Word** | Rapports, notes de contrats, documents et commentaires modifiables |
| **Page web interactive** | Chronologie d'investissements, filtres de projets, dashboard de prix, graphiques explorables |

## 8. Modification de documents Office

L'application peut examiner des fichiers Word/PPT/Excel existants et effectuer les modifications prises en charge : corrections ciblées dans Word, commentaires, organisation de diapositives, contrôles de tableaux et de formules. Les mises en page élaborées et les résultats calculés doivent être contrôlés dans le logiciel Office adapté.

## 9. Navigateur et contrôle humain

Chaque Bot peut utiliser son propre navigateur sur le poste de travail : ouvrir une page, lire les contenus accessibles, cliquer, remplir des champs et restituer des informations. **Connexion, paiements, CAPTCHA et autorisations d'opérations sensibles restent sous contrôle humain**. Les sites étrangers peuvent nécessiter une connexion réseau appropriée ou un proxy.

## 10. Agents et groupes

**50 Bots et 15 groupes prédéfinis** : vente nationale, achats, export, import, étude des entreprises, marchés physiques, futures, quant, rédaction de rapports et contrôle des preuves. Le coordinateur d'un groupe répartit le travail ; mentionnez un spécialiste avec `@` pour le solliciter.

## 11. Installation et connexion

1. Téléchargez **ChemClaw v0.3.0** pour Windows, macOS (Intel/Apple Silicon) ou Linux depuis [GitHub Releases](https://github.com/zoeyzhang233666/chemclaw-bot/releases).
2. Obtenez une clé de modèle sur [APIHub](https://apihub.chem-cloud.cn/) et renseignez-la dans **Paramètres → Modèles → APIHub**. Les formules d'essai et les abonnements nommés « illimités » sont soumis aux tarifs, durées et quotas indiqués sur le site.
3. Obtenez une **clé de données distincte** sur [Chemcloud Data Hub](https://mcp.chem-cloud.cn/) et saisissez-la dans **Paramètres → Connecteurs**.
4. Ouvrez un agent spécialisé ou un groupe et formulez votre besoin métier.

Les utilisateurs de DeepSeek Harness Desktop peuvent également installer [ChemClaw comme plugin](https://github.com/zoeyzhang233666/chemclaw-bot/tree/main/chemclaw-bot).

## 12. Exemples de demandes métier

**Nouveaux clients :**

> Nous vendons du carbonate de sodium dense en Chine orientale. À partir de Chemcloud Data Hub, identifie les verreries en développement, puis vérifie les matières premières dans les EIA, les communiqués de sociétés et les PDF CNINFO. Remets un Excel avec usine, projet, capacité annoncée, état, preuve de consommation, source, date et priorité ; affiche une chronologie dans le chat.

**Appels d'offres actifs :**

> Recherche les avis publiquement accessibles des 30 derniers jours concernant la soude caustique industrielle pour alumine, papier et traitement d'eau. Distingue les offres encore ouvertes des marchés attribués, vérifie concentration, volume, lieu, échéance et URL officielle. Prépare une base Excel pour la prospection.

---

## Avant utilisation

ChemClaw est un **outil d'aide à la recherche et à la décision**, pas un système de passage d'ordres automatiques ni de commande d'installations industrielles. Contrats, qualité, conformité et opérations exigent la vérification des sources primaires. Données et accès doivent être autorisés. Licence **Apache-2.0** ; basé sur **DS Bot / DeepSeek Harness** (voir `NOTICE`).
