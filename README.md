# 🎮 Minesweeper Multiplayer (Démineur Multijoueur)

**Minesweeper Multiplayer** est un bot Discord permettant de jouer au démineur en multijoueur avec un système de tour par tour et des règles adaptées.
Le dernier survivant gagne, et un système de score départage les égalités.

## 📌 Fonctionnalités principales

- 🏁 **Démarrer une partie** : `!boom @player1 @player2 ...` (min 2, max 4 joueurs)
- 📜 **Afficher les règles** : `!boom rules`
- 🎲 **Générer un ordre aléatoire des tours**
- 🗺️ **Afficher la carte** : La carte du jeu est affichée après chaque action.
- ❓ **Révéler une case** : `!r A1` (exemple)
- 🚩 **Placer/enlever un drapeau** : `!f A1` (exemple)
- 🔥 **Élimination** : Si un joueur clique sur une bombe ou viole une règle, il est éliminé.
- 🏆 **Fin du jeu** : Dernier survivant gagne. En cas d’égalité, les drapeaux posés corrects sont comptabilisés.

---

## 🕹️ Règles du jeu

### 📌 Commandes de base
- `!r A1` : Révéler la case **A1**.
- `!f A1` : Placer ou enlever un **drapeau** sur **A1**.
- `!boom @player1 @player2` : **Démarrer une partie** avec au moins 2 joueurs et au plus 4.
- `!boom rules` : Afficher les règles.

### ⚠️ Règles spécifiques
- **On ne peut pas commencer par un drapeau.**  
  → Le premier coup doit être une révélation (`!r A1`) car la première case ne peut pas contenir de bombe.
- **Cliquer sur un drapeau adverse entraîne une élimination :**
  - 💥 **Si la case contient une bombe** → **Le joueur qui a cliqué est éliminé.**
  - ✅ **Si la case est sûre** → **Le joueur qui a posé le drapeau est éliminé.**
- **Dernier survivant gagne** :  
  - Lorsqu'un joueur est éliminé, on continue jusqu'à ce qu'il n'y ait plus qu'un joueur en lice.

### 🎯 Système de scoring en cas d’égalité
Si plusieurs joueurs survivent et que la carte est complétée, on applique le score suivant :
- ✅ +1 point par **drapeau correct** (placé sur une bombe).

Le **classement final** affiche la map révélée avec les scores.

---

### 🏁 Déroulement d’une partie
1. Un joueur démarre une partie avec `!boom @player1 @player2`.
2. Les joueurs jouent à tour de rôle.
3. À chaque action (`!r` ou `!f`), la carte est mise à jour et affichée.
4. Lorsqu’un joueur est éliminé, il est retiré de la partie.
5. Quand il ne reste qu’un joueur, il est **déclaré vainqueur**.  
   Si toutes les cases sûres sont révélées, on applique le système de **score** pour classer les joueurs.

---

## 🐞 Bugs & Optimisations

### 🔧 Corrections implémentées
✅ **Révéler toute la map et afficher un classement en fin de partie**  
✅ **Compteur de bombes restantes** (`total_bombes - drapeaux_posés`)

### 🚀 Optimisations possibles
- Gérer le cas où on flag une case vide qui est reveal avec le flood_real, que pasà ?
- **End Game** remplacement de la case qui a fait perdre un joueur par la version _e de l'emoji

---

## 🚀 Installation & Déploiement

### 1️⃣ Cloner le projet
- ```git clone https://github.com/Jef-Ed/boom-bot```
- ```cd Minesweeper-Multiplayer```

### 2️⃣ Installer les dépendances
- ```pip install -r requirements.txt```

### 3️⃣ Configurer le bot Discord
- Ajoutez votre token Discord dans un fichier de configuration config.yml.
- Vérifiez que votre bot a les permissions pour lire et écrire dans les salons.

### 4️⃣ Lancer le bot
- ```python boomBot.py```