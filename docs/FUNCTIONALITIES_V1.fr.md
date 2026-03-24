# Fonctionnalites V1

Ce document resume les principales fonctionnalites applicatives presentes dans la V1 de `Javis`. Il decrit les usages visibles dans l'application, sans entrer dans le detail complet de l'implementation technique.

## 1. Scan de contenu

L'application permet de scanner un dossier local pour detecter les fichiers a indexer.

Capacites principales :

- lancement d'un scan rapide via l'ouverture d'un dossier ;
- lancement d'un scan avance avec configuration ;
- selection des groupes de fichiers a traiter : documents, images, videos, audio, autres ;
- prise en charge des extensions configurees dans les settings ;
- affichage de la progression et de l'etat de l'operation ;
- annulation d'un scan en cours.

Resultat attendu :

- les fichiers trouves sont ajoutes a la base ;
- un hash de fichier peut etre calcule pour alimenter la detection de doublons ;
- la liste des resultats est rafraichie dans l'interface ;
- les traitements annexes peuvent etre chaines pendant le scan.

## 2. Generation de miniatures et extraction de metadata

Pendant ou apres le scan, l'application peut enrichir les fichiers avec deux traitements complementaires :

- `thumbnails` : generation de miniatures pour l'affichage visuel ;
- `metadata` : extraction des informations techniques et documentaires.

Exemples de donnees gerees :

- taille du fichier ;
- dates ;
- dimensions ;
- format ;
- hash de fichier ;
- annee deduite des metadata ou du systeme de fichiers.

Impact fonctionnel :

- affichage plus riche dans la grille, la liste et l'aperçu ;
- meilleure base pour le tri, le filtrage, la categorisation et l'organisation.

## 3. Detection des doublons via le hash

L'application peut detecter des doublons logiques a partir du hash de fichier stocke en base.

Capacites principales :

- calcul et stockage d'un hash de contenu lors de l'indexation ou de la mise a jour ;
- regroupement des fichiers partageant le meme hash ;
- exposition du nombre de doublons dans les donnees de contenu ;
- reutilisation possible de cette information dans certains traitements metier.

Usages fonctionnels :

- identifier plusieurs fichiers ayant le meme contenu meme si leur nom differe ;
- faciliter l'analyse de la bibliotheque avant organisation ;
- reduire des traitements inutiles sur des fichiers deja connus.

Dans l'etat actuel de la V1, cette detection sert notamment de support a la categorisation :

- si un fichier partage le meme hash qu'un fichier deja categorise ;
- la categorisation existante peut etre reutilisee pour eviter un nouvel appel LLM.

## 4. Categorisation automatique

L'application permet de categoriser automatiquement les fichiers via la couche LLM.

Capacites principales :

- categorisation depuis la vue courante ;
- configuration des categories disponibles ;
- prise en charge des images et des documents ;
- mode apercu ou traitement complet ;
- seuil de confiance ;
- option pour ne traiter que les fichiers non encore categorises ;
- enregistrement du resultat dans la base.

Resultat attendu :

- chaque fichier peut recevoir une categorie ;
- le niveau de confiance et les details d'extraction sont conserves ;
- des doublons detectes par hash peuvent reutiliser une categorisation existante ;
- les categories peuvent ensuite etre utilisees dans le filtrage et l'organisation.

## 5. Organisation automatique

L'application peut reorganiser les fichiers selon plusieurs strategies.

Capacites principales :

- selection d'un dossier cible ;
- mode `copy` ou autre action selon la configuration ;
- organisation par categorie ;
- organisation par annee ;
- organisation par type ;
- organisations combinees, par exemple categorie/annee ou type/categorie ;
- mode apercu avant execution ;
- suivi de progression pendant l'operation.

Resultat attendu :

- creation d'une arborescence cible coheree ;
- deplacement ou copie des fichiers selon la strategie choisie ;
- retour d'un resume final des fichiers traites, reussis ou en erreur.

### Alerte V1 sur le mode `move`

Pour la V1, le mode `copy` doit etre considere comme le mode recommande.

Le mode `move` existe, mais il ne doit pas encore etre traite comme un flux de consolidation definitif sans verification complementaire. En particulier, une vigilance est necessaire sur la synchronisation entre le deplacement physique du fichier et l'etat en base de donnees.

En pratique :

- `copy` est adapte pour consolider une bibliotheque sans risque de perdre la source ;
- `move` devra etre fiabilise en V2 pour devenir le mode normal de suppression des redondances et de regroupement final dans une arborescence unique.

## 6. Filtrage des resultats

L'utilisateur peut affiner les resultats affiches dans l'interface sans relancer un scan.

Filtres disponibles :

- type de fichier ;
- categorie ;
- annee ;
- extension.

Capacites associees :

- combinaison de plusieurs filtres ;
- remise a zero des filtres ;
- mise a jour immediate de la liste visible ;
- coherence entre la vue courante et les operations lancees ensuite.

Usage attendu :

- isoler rapidement un sous-ensemble de fichiers ;
- lancer une categorisation ou une organisation sur la vue deja filtree.

## 7. Configuration et settings

L'application integre un ecran de configuration centralise.

Parametres fonctionnels notables :

- langue ;
- theme ;
- URL API ;
- timeouts et retries ;
- modeles LLM image et document ;
- prompts ;
- extensions de scan ;
- categories ;
- seuil de confiance ;
- parametres lies aux miniatures et au pretraitement.

Resultat attendu :

- les parametres sont persistants ;
- les composants de l'application relisent ces reglages sans dupliquer la logique de configuration ;
- la configuration pilote directement le comportement du scan et de la categorisation.

## 8. Details d'image / fichier

L'application propose une vue de detail sur un fichier selectionne.

Capacites principales :

- ouverture d'un dialogue de details depuis les vues de resultats ;
- affichage d'un apercu adapte au fichier ;
- affichage des informations associees au fichier ;
- navigation vers le fichier precedent et suivant ;
- navigation clavier gauche / droite dans le dialogue de details.

Ce point est important pour la V1 car il permet un controle visuel rapide sans sortir du flux principal.

## 9. Navigation dans les vues

L'interface propose plusieurs modes de navigation dans les resultats.

Modes disponibles :

- vue grille ;
- vue liste ;
- vue colonnes.

Fonctionnalites de navigation associees :

- changement de mode d'affichage ;
- recherche textuelle ;
- tri des resultats ;
- zoom dans la grille ;
- selection d'un fichier ;
- activation d'un fichier pour ouvrir le detail.

Objectif :

- permettre a l'utilisateur de passer d'une navigation visuelle a une navigation plus tabulaire selon le contexte.

## 10. Resume de la chaine fonctionnelle

La chaine d'usage principale de la V1 est la suivante :

```text
Scanner -> enrichir (metadata + thumbnails) -> naviguer -> filtrer
-> categoriser -> organiser
```

Les settings pilotent cette chaine a plusieurs niveaux :

- ce qui est scanne ;
- comment les fichiers sont interpretes ;
- comment la categorisation est realisee ;
- comment l'organisation finale est construite.
