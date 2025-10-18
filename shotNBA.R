# installa devtools se non lo hai
install.packages("devtools")

# installa nbastatR da GitHub
devtools::install_github("abresler/nbastatR")

library(nbastatR)

Sys.setenv("VROOM_CONNECTION_SIZE" = 10000000) 

# esempi
players <- nba_players()
teams <- nba_teams()
stats <- game_logs(seasons = 2025, result_types = "player")

shots_2025 <- player_shots(seasons = 2025, season_types = "Regular Season")
