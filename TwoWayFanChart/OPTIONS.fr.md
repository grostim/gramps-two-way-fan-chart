# Éventail généalogique bidirectionnel — Référence des options

Ce document décrit chaque option configurable du rapport Éventail
généalogique bidirectionnel **et son effet réel sur le rendu**. Il est
maintenu synchronisé avec le menu d'options par un test automatisé
(`tests/test_option_contract.py`) : chaque option du menu doit avoir
une section ici, et chaque section doit correspondre à une option
existante du menu. Lorsque vous ajoutez, supprimez ou renommez une
option, mettez à jour ce fichier (et sa version anglaise
`OPTIONS.md`) dans le même changement.

Le menu du rapport est organisé par catégories. Les options ajoutées
par Gramps lui-même (traitement des données privées et des personnes
vivantes) sont documentées à la fin.

---

## Sujet et générations

### preset
- Type : liste — `publication`, `compact`, `custom`
- Défaut : `publication`

Applique un profil complet de configuration en un clic.

- `publication` — le profil maquette public : papier A0 paysage,
  5 générations d'ancêtres + 4 de descendants, options de
  confidentialité ouvertes, portraits actifs, marqueurs désactivés.
- `compact` — papier A4, 2 générations d'ancêtres + 1 de descendants,
  pour un aperçu rapide de type fiche familiale.
- `custom` — le profil n'est plus un préréglage ; le graphique utilise
  exactement les valeurs affichées dans le menu.

Toute modification manuelle d'une valeur contrôlée par un préréglage
bascule automatiquement le preset sur `custom` (le graphique conserve
votre nouvelle valeur).

### center_family
- Type : sélecteur de famille
- Défaut : valeur mémorisée, ou première famille de l'arbre

Sélectionne le couple dessiné au centre du graphique. Le médaillon de
gauche est le père, celui de droite la mère (quand les deux existent).
Les ancêtres s'éventillent au-dessus, les descendants en dessous.

### ancestor_generations
- Type : nombre, 0–8
- Défaut : `5`

Nombre de générations d'ancêtres dessinées dans l'éventail supérieur.
`0` masque entièrement l'éventail des ancêtres. La mise en page réserve
un anneau radial par génération et adapte le détail des libellés à
l'espace disponible.

### descendant_generations
- Type : nombre, 0–5
- Défaut : `4`

Nombre de générations de descendants dessinées dans l'éventail
inférieur. `0` masque entièrement l'éventail des descendants. Les
générations plus profondes ne sont dessinées que si le format de papier
laisse assez de place pour un secteur lisible.

---

## Personnes et familles

### parent_family_policy
- Type : liste — `primary`, `biological`, `first`
- Défaut : `primary`

Quelle famille suivre quand une personne est enfant de plusieurs
familles.

- `primary` — la famille dont la relation de conjoint est marquée
  principale dans Gramps.
- `biological` — la famille où la naissance/interaction de la personne
  est marquée biologique (lien de naissance), quand c'est enregistré.
- `first` — la première famille listée pour la personne dans la base.

### descendant_family_policy
- Type : liste — `all`, `primary`, `first`
- Défaut : `all`

Quelles familles développer quand une personne a plusieurs unions.

- `all` — chaque union enregistrée produit une branche descendante.
- `primary` — seule l'union marquée principale dans Gramps.
- `first` — seule la première union enregistrée.

### show_ancestor_marriages
- Type : booléen
- Défaut : `true`

Quand activée, chaque anneau de génération d'ancêtres gagne des
secteurs intermédiaires compacts affichant le symbole de mariage (⚭),
l'année et le lieu enregistrés de chaque couple parental. Le libellé
est omis quand les règles de confidentialité ne permettent pas de
montrer le couple.

### show_descendant_marriages
- Type : booléen
- Défaut : `true`

Quand activée, des secteurs d'union sont insérés après chaque
génération de descendants, affichant le symbole de mariage (⚭),
l'année et le lieu enregistrés. À partir de la deuxième génération, la
bande porte deux lignes — la date sur la première, le lieu sur la
seconde — afin qu'un secteur éloigné conserve le lieu au lieu de
l'abandonner. La bande des enfants directs reste sur une seule ligne.
Quand un secteur est trop étroit pour deux lignes lisibles, la bande
ne garde qu'une ligne, avec le symbole de mariage et l'année.

---

## Noms

### name_format
- Type : liste — format actuel du rapport, défaut Gramps ou format Gramps disponible
- Défaut : `current_report`

Contrôle l'affichage des noms du couple central, des ancêtres et des
descendants.

- `current_report` conserve exactement l'affichage existant du rapport,
  notamment le prénom d'usage et le surnom. C'est le défaut : les
  configurations enregistrées gardent ainsi leur apparence.
- `Gramps default` utilise le format de nom choisi dans les préférences
  Gramps.
- Tout autre choix applique le format Gramps correspondant à ce rapport
  uniquement, sans modifier la préférence globale.

---

## Portraits et médaillons

### show_portraits
- Type : booléen
- Défaut : `true`

Dessine le médaillon de portrait de chaque personne visible. Quand
désactivé, les médaillons affichent un substitut (initiales ou
silhouette). Toutes les sous-options de portrait ci-dessous ne sont
actives que si cette option est activée.

### portrait_source
- Type : liste — `first_image`, `tagged_portrait`, `primary`
- Défaut : `first_image`

Quel média de la personne utiliser comme portrait.

- `first_image` — le premier média de type image dans l'ordre Gramps.
- `tagged_portrait` — la première référence média portant l'attribut
  personnalisé documenté `portrait` avec une valeur vraie.
- `primary` — uniquement le média marqué principal dans Gramps.

La première image utilisable de la sélection est retenue, dans l'ordre
Gramps.

### respect_media_crop
- Type : booléen
- Défaut : `true`

Quand activé, le rectangle de recadrage enregistré sur la référence
média est appliqué avant le centrage carré. Quand désactivé, l'image
complète est utilisée.

### portrait_treatment
- Type : liste — `color`, `grayscale`, `sepia`
- Défaut : `color`

Rendu couleur du portrait : couleurs d'origine, niveaux de gris, ou
bichromie sépia.

---

## Papier et mise en page

### paper_size
- Type : liste — A5, A4, A3, A2, A1, A0, Letter, Legal, Tabloid,
  Custom
- Défaut : `A0`

Format de papier standard du graphique. Choisir `Custom` active les
deux dimensions personnalisées ci-dessous.

### orientation
- Type : liste — `portrait`, `landscape`
- Défaut : `landscape`

Échange la largeur et la hauteur du papier. L'éventail étant plus large
que haut, le paysage est l'orientation recommandée.

### margin_mm
- Type : nombre (mm), 0–100
- Défaut : `12`

Marge uniforme autour du graphique. La zone de dessin est le papier
moins ces marges sur les quatre côtés.

### custom_width_mm
- Type : nombre (mm), 1–2000
- Défaut : `594`
- Disponible uniquement quand `paper_size` vaut `Custom`.

Largeur du format de papier personnalisé.

### custom_height_mm
- Type : nombre (mm), 1–2000
- Défaut : `420`
- Disponible uniquement quand `paper_size` vaut `Custom`.

Hauteur du format de papier personnalisé.

---

## Couleurs et styles

### background_color
- Type : couleur
- Défaut : `#FAF9F5`

Couleur de fond du graphique (couleur du papier). Elle est utilisée
comme fond de la page SVG et comme fond du PDF/PNG.

### highlight_tag
- Type : chaîne (nom d'étiquette Gramps)
- Défaut : vide

Quand `show_highlight_markers` est activé, les personnes portant cette
étiquette Gramps sont visuellement marquées sur le graphique. Une
valeur vide désactive le marquage même si l'option des marqueurs est
activée.

### show_highlight_markers
- Type : booléen
- Défaut : `false`

Dessine un marqueur autour des médaillons centraux, des emplacements
d'ancêtres et des médaillons de descendants dont la personne porte
l'étiquette `highlight_tag` configurée. Le marqueur est automatiquement
effacé pour les personnes masquées ou exclues, afin qu'aucun signal ne
filtre à travers la confidentialité.

### highlight_source_ok_dates
- Type : booléen
- Défaut : `false`

Quand elle est activée, les dates de naissance ou de décès dont
l'événement porte exactement l'étiquette Gramps `Source OK` sont
affichées en vert vif. L'option respecte la confidentialité et conserve
le gris par défaut quand elle est désactivée.

---

## Confidentialité

### privacy_mode
- Type : liste — `include_all`, `full_name_only`,
  `replace_identity`, `exclude`, `publication_safe`
- Défaut : `include_all`

Politique appliquée aux personnes **marquées privées** dans la base.
Elle n'a d'effet que lorsque « Inclure les données marquées privées »
est décoché (ou quand `publication_safe` est sélectionné).

- `include_all` — les personnes privées sont affichées normalement.
- `full_name_only` — le nom complet est conservé, dates et portraits
  sont retirés.
- `replace_identity` — l'identité est remplacée par le substitut
  générique « Personne privée ».
- `exclude` — la personne disparaît complètement du graphique.
- `publication_safe` — le profil combiné le plus strict : personnes
  privées et vivantes masquées quelles que soient les autres options,
  libellés de mariage des familles protégées supprimés.

### incl_private
*(option standard Gramps)*
- Type : booléen
- Défaut : `true` (coché)

Indique si les informations marquées privées dans la base sont
incluses. Quand décoché, les personnes privées sont filtrées selon
`privacy_mode`.

### living_people
*(option standard Gramps)*
- Type : liste — `include_all`, `include_last_name_only`,
  `include_full_name_only`, `replace_complete_name`, `exclude_all`
- Défaut : `include_all`

Comment sont traitées les personnes vivantes.

- `include_all` — les personnes vivantes sont affichées normalement.
- `include_last_name_only` — seul le nom de famille est conservé,
  toutes les autres données personnelles (prénoms, dates, portrait)
  sont retirées.
- `include_full_name_only` — le nom complet est conservé, toutes les
  autres données sont retirées.
- `replace_complete_name` — l'identité est remplacée par le substitut
  Gramps pour données privées.
- `exclude_all` — les personnes vivantes sont retirées complètement du
  graphique.

### years_past_death
*(option standard Gramps)*
- Type : nombre (années), ≥ 0
- Défaut : `0`

Nombre d'années après le décès d'une personne au-delà duquel elle
n'est plus considérée comme vivante, pour le filtre des personnes
vivantes ci-dessus. `0` signifie que seules les personnes avec une date
de décès enregistrée sont considérées décédées.

---

## Sortie

Le format de sortie du rapport (SVG, PDF, PNG) est **toujours**
déterminé par l'extension du fichier de sortie choisi par la boîte de
dialogue du rapport, la ligne de commande ou Gramps Web. Ce module ne
propose pas d'option de format dédiée dans son menu.
