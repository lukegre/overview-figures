# Libs
library(tidyverse)
library(ggrepel)
library(cowplot)
library(calecopal)
library(cowplot)

# Tuto chart
# https://stackoverflow.com/questions/73333971/3-layer-donut-chart-in-r

# Types of fjord
fjord_glace <- c("GF23_B_355m_edna", "GF23_B_2m_edna", "GF23_D_600m_edna", "GF23_D_2m_edna", 
                 "GF23_E_180m", "GF23_E_2m", "GF23_K_2m", "GF23_K_630m")
fjord_land <- c("GF23_V_2m", "GF23_V_240m", "GF23_W_2m", "GF23_W_380m", "GF23_Z_2m" , "GF23_Z_260m")

# Correct identity
gadus_morua <- c("CACCGCGGTTATACGAGAGGCCCAAATTGATGAAGAACGGCGTAAAGCGTGGTTAAGAAAAAAGAGAAAATATGGCCGAACAGCTTCAAAGCAGTTATACGCATCCGAAGTCACGAAGAACAATCACGAAAGTTGCCCTAAAACCTCCGATTCCACGAGAGCCATAAAA", 
                 "CACCGCGGTTATACGAGAGGCCCTAATTGATGAAGAACGGCGTAAAGCGTGGTTAAGAAAAAAGAGAAAATATGGCCGAACAGCTTCAAAGCAGTTATACGCATCCGAAGTCACGAAGAACAATCACGAAAGTTGCCCTAAAACCTCCGATTCCACGAAAGCCATAAAA")

# ------------------------------------------------------------- # 
# FORMAT DATA 

# Read data
fish <- read.csv("data/edna/share_mifish_greenfjord_tablefull.csv") |> 
  mutate(fjord_type = case_when(
    ID.Number %in% fjord_glace ~ "ice", 
    TRUE ~ "land"
  )) |> 
  # Remove the other fjord
  filter(!grepl("180", ID.Number)) |> 
  # Correct assignments
  mutate(scientific_name = case_when(
    sequence %in% gadus_morua ~ "Gadus morhua", 
    TRUE ~ scientific_name
  ))

plankton <- read.csv("data/edna/share_eukatara_table.csv") |> 
  mutate(fjord_type = case_when(
    ID.Number %in% fjord_glace ~ "ice", 
    TRUE ~ "land"
  )) |> 
  # Remove the other fjord
  filter(!grepl("180", ID.Number))

write.table(plankton, 
            "output_plankton_GF2023.tsv", row.names = F, quote = F, sep = "\t")

# Format data then link both 
fish_keep <- c("Anarhichas", "Mallotus villosus", "Gadus morhua", "Sebastes mentella", "Sebastes", "Reinhardtius hippoglossoides", "Cyclopterus lumpus")

fish2 <- fish |> 
  # Keep only the wanted species 
  filter(scientific_name %in% fish_keep) |> 
  rename(depth = Sampling.depth..m.) |> 
  mutate(vernacular_name = case_when(
    scientific_name == "Anarhichas" ~ "Wolfish", 
    scientific_name == "Mallotus villosus" ~ "Capelin", 
    scientific_name == "Gadus morhua" ~ "Atlantic cod", 
    scientific_name %in% c("Sebastes mentella", "Sebastes") ~ "Redfish", 
    scientific_name == "Reinhardtius hippoglossoides" ~ "Greenland halibut", 
    scientific_name == "Cyclopterus lumpus" ~ "Lumpfish"
  )) |> 
  # Now sum by name
  group_by(vernacular_name, deep_surface, fjord_type,ID.Number, depth) |> summarise(count = sum(count)) |> ungroup() |> 
  dplyr::select(vernacular_name, deep_surface, fjord_type, ID.Number, count, depth) |> 
  # Format now
  group_by(ID.Number) |> 
  mutate(tot_count = sum(count),
    percentage_reads = round(count/tot_count*100, 1)) |> 
  # Add the distance to ice 
  mutate(dist_from_glacier = case_when(
    ID.Number %in% c("GF23_B_355m_edna", "GF23_B_2m_edna") ~ 27,
    ID.Number %in% c("GF23_D_2m_edna", "GF23_D_600m_edna") ~ 57,
    ID.Number %in% c("GF23_K_630m", "GF23_K_2m") ~ 92,
    ID.Number %in% c("GF23_Z_260m", "GF23_Z_2m") ~ 7,
    ID.Number %in% c("GF23_W_2m", "GF23_W_380m") ~ 30,
    ID.Number %in% c("GF23_V_240m", "GF23_V_2m") ~ 58
  )) |> ungroup() |> filter(!is.na(dist_from_glacier)) |> 
  mutate(type = "fish")

plankton2 <- plankton |> 
  # Keep only the wanted species 
  rename(depth = Sampling.depth..m.) |> 
  dplyr::select(Class, deep_surface, fjord_type, ID.Number, count, depth) |> 
  # Format now
  group_by(ID.Number) |> 
  mutate(tot_count = sum(count),
         percentage_reads = round(count/tot_count*100, 1)) |> 
  # Add the distance to ice 
  mutate(dist_from_glacier = case_when(
    ID.Number %in% c("GF23_B_355m_edna", "GF23_B_2m_edna") ~ 27,
    ID.Number %in% c("GF23_D_2m_edna", "GF23_D_600m_edna") ~ 57,
    ID.Number %in% c("GF23_K_630m", "GF23_K_2m") ~ 92,
    ID.Number %in% c("GF23_Z_260m", "GF23_Z_2m") ~ 7,
    ID.Number %in% c("GF23_W_2m", "GF23_W_380m") ~ 30,
    ID.Number %in% c("GF23_V_240m", "GF23_V_2m") ~ 58
  )) |> ungroup() |> filter(!is.na(dist_from_glacier))

# Get only the 4 more abundant per sample 
plankton3 <- plankton2 %>%
  group_by(ID.Number) %>%
  mutate(rank = rank(-count, ties.method = "first")) %>% # Rank Classes by count (descending)
  mutate(Class = ifelse(rank > 6, "others", Class)) %>%  # Replace ranks > 4 with "others"
  group_by(ID.Number, Class, .add = TRUE) %>%
  summarise(
    count = sum(count),                         # Sum counts for each Class (including "others")
    .groups = "drop"
  ) %>%
  group_by(ID.Number) %>%
  mutate(
    percentage_reads = (count / sum(count)) * 100 # Recalculate percentage_reads to ensure it sums to 100
  ) %>%
  mutate(percentage_reads = round(percentage_reads, 0)) |> 
  ungroup() %>%
  arrange(ID.Number, desc(count))  |> 
  mutate(type = "plankton") |> 
  select(-count) |> 
  # Link rest of data
  left_join(plankton2 |> distinct(ID.Number, fjord_type, depth, dist_from_glacier)) |> 
  dplyr::select(ID.Number, Class, percentage_reads, type, fjord_type, depth, dist_from_glacier)

# Ready to assemble 
fish3 <- fish2 |> 
  rename(Class = vernacular_name) |> 
  dplyr::select(ID.Number, Class, percentage_reads, type, fjord_type, depth, dist_from_glacier)
  
# Join plankton and fish and make a fist plot - double donut 
both <- rbind(fish3, plankton3) |> 
  mutate(Class = ifelse(is.na(Class), "NA", Class))

both_ice <- both |> filter(fjord_type == "ice")
both_land <- both |> filter(fjord_type == "land")

###### 
corresp <- plankton3 |> 
  distinct(ID.Number, depth, dist_from_glacier, fjord_type)

# ------------------------------------------------------------- # 
# PLOT 

# Colors for fish and plankton
# 6 fish colors 
# 10 plankton color + 1 grey

library(harrypotter)
#library(paletteer)

#pal_p <- cal_palette(name = "arbutus", n = 10, type = "continuous")
#pal_f <- cal_palette(name = "figmtn", n = 6, type = "continuous")

pal_p <- hp(n = 10, house = "Sprout")
#pal_f <- hp(n = 6, house = "Always")
pal_f <- c("#BFBFBFFF", "#A1B7BFFF", "#80AEBEFF", "#58A6BEFF", "#80AEE7", "#009DBDFF")

# Colors
colors_all <- c(
  "Redfish" = pal_f[1],
  "Capelin" = pal_f[2],
  "Greenland halibut" = pal_f[3],
  "Lumpfish" = pal_f[4],
  "Wolfish" = pal_f[5],
  "Atlantic cod" = pal_f[6],
  "others" = pal_p[10],
  "Ciliophora" = pal_p[1],
  "Dinoflagellata" = pal_p[2],
  "Metazoa" = pal_p[3],
  "Ochrophyta" = pal_p[4],
  "NA" = "grey70",
  "Haptophyta" = pal_p[5],
  "Pseudofungi" = pal_p[6],
  "Lobosa" = pal_p[7],
  "Chlorophyta" = pal_p[8],
  "Radiolaria" = pal_p[9]
)

# Now loop over to create the plots - one list for each fjord

# Ice fjord
plots_ice <- lapply(unique(both_ice$ID.Number), function(x){
  
  # Filter
  df <- both_ice |> 
    filter(ID.Number == x)
  
  # Clean
  p <- ggplot(df, aes(x = type, y = percentage_reads, fill = Class)) +
    geom_col() +
    scale_x_discrete(limits = c(" ", "fish","plankton")) +
    theme_minimal()+
    coord_polar("y")+ 
    geom_label_repel(aes(label = Class),
                     position = position_stack(vjust = 0.5),
                     show.legend = FALSE) + 
    theme_void() + 
    scale_fill_manual(values =colors_all ) + theme(legend.position = "none")
  
  return(p)
})

names(plots_ice) <- unique(both_ice$ID.Number)

# Land fjord
plots_land <- lapply(unique(both_land$ID.Number), function(x){
  
  # Filter
  df <- both_land |> 
    filter(ID.Number == x)
  
  # Clean
  p <- ggplot(df, aes(x = type, y = percentage_reads, fill = Class)) +
    geom_col() +
    scale_x_discrete(limits = c(" ", "fish","plankton")) +
    theme_minimal()+
    coord_polar("y")+ 
    geom_label_repel(aes(label = Class),
                     position = position_stack(vjust = 0.5),
                     show.legend = FALSE) + 
    theme_void() + 
    scale_fill_manual(values =colors_all ) + theme(legend.position = "none") #+ ggtitle(x) +  theme(plot.title = element_text(hjust = 0.5))
  
  return(p)
})

# Name elements of list 
names(plots_land) <- unique(both_land$ID.Number)

# ------------------------------------------------ # 
# Land plot 

# Main plot
baseplot1 <- ggplot() + 
  xlab("Distance to glacier (km)") + ylab("Depth (m)") + 
  scale_y_reverse(limits = c(550, -150), expand = c(0,0), breaks = c(0, 200, 400)) + 
  scale_x_continuous(limits = c(-15, 75), expand = c(0,0)) +
  theme_minimal() + 
  theme(panel.background = element_rect(fill = "white",
                                 colour = "black",
                                 size = 0.5, linetype = "solid"),
        panel.grid.minor = element_blank()) + 
  ggtitle("Land fjord") + 
  geom_point(data = corresp |> filter(fjord_type == "land"), aes(x = dist_from_glacier, y = depth))

p_land <- ggdraw() +
  draw_plot(baseplot1) +
  draw_plot(plots_land[[corresp[[7,"ID.Number"]]]], x = 0.6, y = 0.25, width = 0.4, height = 0.4) + 
  draw_plot(plots_land[[corresp[[8,"ID.Number"]]]], x = 0.6, y = 0.60, width = 0.4, height = 0.4) + 
  draw_plot(plots_land[[corresp[[9,"ID.Number"]]]], x = 0.31, y = 0.60, width = 0.4, height = 0.4) + 
  draw_plot(plots_land[[corresp[[10,"ID.Number"]]]], x = 0.3, y = 0.06, width = 0.4, height = 0.4) + 
  draw_plot(plots_land[[corresp[[11,"ID.Number"]]]], x = 0.05, y = 0.24, width = 0.4, height = 0.4) + 
  draw_plot(plots_land[[corresp[[12,"ID.Number"]]]], x = 0.03, y = 0.6, width = 0.4, height = 0.4) 
p_land

ggsave("plots/donut_chart_land_1.png", p_land, width = 12, height = 8)

# ------------------------------------------------ # 
# Ice plot 

# Main plot
baseplot1_ice <- ggplot() + 
  xlab("Distance to glacier (km)") + ylab("Depth (m)") + 
  scale_y_reverse(limits = c(850, -200), expand = c(0,0), breaks = c(0, 200, 400, 600)) + 
  scale_x_continuous(limits = c(-5, 115), expand = c(0,0)) +
  theme_minimal() + 
  theme(panel.background = element_rect(fill = "white",
                                        colour = "black",
                                        size = 0.5, linetype = "solid"),
        panel.grid.minor = element_blank()) + 
  geom_point(data = corresp |> filter(fjord_type == "ice"), aes(x = dist_from_glacier, y = depth), col = "black") + 
  ggtitle("Glacial fjord") + ylab("")

p_ice <- ggdraw() +
  draw_plot(baseplot1_ice) +
  draw_plot(plots_ice[[corresp[[1,"ID.Number"]]]], x = 0.10, y = 0.60, width = 0.4, height = 0.4) + 
  draw_plot(plots_ice[[corresp[[2,"ID.Number"]]]], x = 0.10, y = 0.26, width = 0.4, height = 0.4) +
  draw_plot(plots_ice[[corresp[[3,"ID.Number"]]]], x = 0.34, y = 0.60, width = 0.4, height = 0.4) +
  draw_plot(plots_ice[[corresp[[4,"ID.Number"]]]], x = 0.33, y = 0.05, width = 0.4, height = 0.4) + 
  draw_plot(plots_ice[[corresp[[5,"ID.Number"]]]], x = 0.62, y = 0.60, width = 0.4, height = 0.4) + 
  draw_plot(plots_ice[[corresp[[6,"ID.Number"]]]], x = 0.62, y = 0.03, width = 0.4, height = 0.4)

ggsave("plots/donut_chart_ice_1.png",p_ice, width = 12, height = 8)

# ============================ # 
# Combine both 

library(patchwork)

p_both <- p_land + p_ice 

ggsave("plots/donut_chart_land_ice1.png", p_both, width = 18, height = 7)


# ---------------------------------------------------- # 
# Plot without labels but with legend

get_legend_35 <- function(plot) {
  # return all legend candidates
  legends <- get_plot_component(plot, "guide-box", return_all = TRUE)
  # find non-zero legends
  nonzero <- vapply(legends, \(x) !inherits(x, "zeroGrob"), TRUE)
  idx <- which(nonzero)
  # return first non-zero legend if exists, and otherwise first element (which will be a zeroGrob) 
  if (length(idx) > 0) {
    return(legends[[idx[1]]])
  } else {
    return(legends[[1]])
  }
}

plot_fish <- ggplot(both |> filter(type == "fish"), aes(x = type, y = percentage_reads, fill = Class)) + 
  geom_col() + scale_fill_manual(values = colors_all, name = "Fish") + theme(legend.position = "bottom") + guides(fill = guide_legend(nrow = 1))

plot_plankton <- ggplot(both |> filter(type == "plankton"), aes(x = type, y = percentage_reads, fill = Class)) + 
  geom_col() + scale_fill_manual(values = colors_all, name = 'Plankton')+ theme(legend.position = "bottom") + guides(fill = guide_legend(nrow = 1))

legend_fish <- get_legend_35(plot_fish)
legend_plankton <- get_legend_35(plot_plankton)

# Make p_land and p_ice without labels
# Ice fjord
plots_ice_nolabel <- plots_ice
plots_land_nolabel <- plots_land

plots_ice_nolabel <- lapply(plots_ice_nolabel, function(x) {
  x |> ggedit::remove_geom('LabelRepel', 1)
})

plots_land_nolabel <- lapply(plots_land_nolabel, function(x) {
  x |> ggedit::remove_geom('LabelRepel', 1)
})

# Assemble
p_land_nolabel <- ggdraw() +
  draw_plot(plots_land_nolabel[[corresp[[7,"ID.Number"]]]], x = 0.6, y = 0.25, width = 0.4, height = 0.4) + 
  draw_plot(plots_land_nolabel[[corresp[[8,"ID.Number"]]]], x = 0.6, y = 0.60, width = 0.4, height = 0.4) + 
  draw_plot(plots_land_nolabel[[corresp[[9,"ID.Number"]]]], x = 0.31, y = 0.60, width = 0.4, height = 0.4) + 
  draw_plot(plots_land_nolabel[[corresp[[10,"ID.Number"]]]], x = 0.3, y = 0.06, width = 0.4, height = 0.4) + 
  draw_plot(plots_land_nolabel[[corresp[[11,"ID.Number"]]]], x = 0.05, y = 0.24, width = 0.4, height = 0.4) + 
  draw_plot(plots_land_nolabel[[corresp[[12,"ID.Number"]]]], x = 0.03, y = 0.6, width = 0.4, height = 0.4) +
  draw_plot(baseplot1 + theme_minimal()) 
  
p_land_nolabel

p_ice_nolabel <- ggdraw() +
  draw_plot(baseplot1_ice) +
  draw_plot(plots_ice_nolabel[[corresp[[1,"ID.Number"]]]], x = 0.10, y = 0.60, width = 0.4, height = 0.4) + 
  draw_plot(plots_ice_nolabel[[corresp[[2,"ID.Number"]]]], x = 0.10, y = 0.26, width = 0.4, height = 0.4) +
  draw_plot(plots_ice_nolabel[[corresp[[3,"ID.Number"]]]], x = 0.34, y = 0.60, width = 0.4, height = 0.4) +
  draw_plot(plots_ice_nolabel[[corresp[[4,"ID.Number"]]]], x = 0.33, y = 0.05, width = 0.4, height = 0.4) + 
  draw_plot(plots_ice_nolabel[[corresp[[5,"ID.Number"]]]], x = 0.62, y = 0.60, width = 0.4, height = 0.4) + 
  draw_plot(plots_ice_nolabel[[corresp[[6,"ID.Number"]]]], x = 0.62, y = 0.03, width = 0.4, height = 0.4)
 
# Make the plot 
p_both2 <- plot_grid(p_land_nolabel, p_ice_nolabel, 
                     legend_plankton, legend_fish,
                     rel_heights = c(1, 0.2))

p_both2

ggsave("plots/donut_chart_land_ice2_legend.png", p_both2, width = 18, height = 7)










