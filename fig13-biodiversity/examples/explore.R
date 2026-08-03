# Lib
library(tidyverse)

# Read and plot 
file <- read.csv("data/fish_catch/FIX012_20241112-130447.csv")

# Aggregate by boat type 
file2 <- file |>
  mutate(clean_landings = as.numeric(na_if(Total.landings.of.fish.and.shellfish, "-"))) |> 
  #filter(district == "Narsaq") |> 
  group_by(district, species, time) |> 
  summarise(sum_landings = sum(clean_landings, na.rm = T)) |> ungroup() |> 
  filter(sum_landings > 0)


# stacked area chart
p1 <- ggplot(file2, aes(x=time, y=sum_landings, fill=species)) + 
  geom_area() + 
  facet_wrap(~district) + 
  theme_bw()

p1

ggsave("plots/fish_explo1.png", p1)

# Colors
fish_colors <- c("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                 "#9467bd", "#8c564b", "#e377c2", "#7f7f7f")
fish_colors <- c("#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
                     "#59a14f", "#edc948", "#af7aa1", "#ff9da7")

pal_f <- c("#BFBFBFFF", "#A1B7BFFF", "#80AEBEFF", "#58A6BEFF", "#80AEE7", "#009DBDFF")

# Colors
fish_colors <- c(
  "Redfish" = pal_f[1],
  "Capelin" = pal_f[2],
  "Greenland halibut" = pal_f[3],
  "Lumpfish" = pal_f[4],
  "Wolfish" = pal_f[5],
  "Atlantic cod" = pal_f[6],
  "Chars" = "#1f77b4",
  "Snow crab" = "#ff9da7"
)


# Ridge line plot
p2 <- ggplot(file2, aes(x = time, y = sum_landings, fill = species)) +
  geom_bar(stat = "identity") +
  facet_grid(district ~ species) +
  theme_bw()+ 
  scale_fill_manual(values = fish_colors) +
  xlab("") +
  theme(
    legend.position="none",
    panel.grid.major = element_blank(),panel.grid.minor = element_blank(),
    strip.background = element_rect(color=NA, fill="grey95", size=1.5, linetype="solid"), 
    strip.text = element_text(size = 8)
  ) 

p2

ggsave("plots/fish_explo2.png", p2, width = 8, heigh = 3)




