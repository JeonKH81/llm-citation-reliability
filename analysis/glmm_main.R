# Confirmatory primary analysis (D11) — web-search arm
# Mixed-effects logistic: problematic ~ model * resource_tier + (1|topic) + (1|review)
suppressMessages({
  if (!requireNamespace("emmeans", quietly=TRUE))
    install.packages("emmeans", repos="https://cloud.r-project.org", quiet=TRUE)
  library(lme4); library(emmeans)
})
emm_options(lmerTest.limit=Inf, pbkrtest.limit=Inf)

d <- read.csv("refdata_main.csv", stringsAsFactors=FALSE)
d$model <- relevel(factor(d$model), ref="gpt")              # gpt = reference (lowest)
d$tier  <- factor(d$tier, levels=c("low","moderate","high"))
d$tier_o <- factor(d$tier, levels=c("low","moderate","high"), ordered=TRUE)
cat("N refs:", nrow(d), "| reviews:", length(unique(d$review)),
    "| topics:", length(unique(d$topic)), "\n\n")

cat("=== crude problematic rate by model x tier ===\n")
print(round(100*tapply(d$problematic, list(d$model, d$tier), mean), 1))

## Primary GLMM (interaction)
m_full <- glmer(problematic ~ model*tier + (1|topic) + (1|review),
                data=d, family=binomial,
                control=glmerControl(optimizer="bobyqa", optCtrl=list(maxfun=2e5)))
m_noint <- update(m_full, . ~ model + tier + (1|topic) + (1|review))
m_nomod <- update(m_full, . ~ tier + (1|topic) + (1|review))
m_notier<- update(m_full, . ~ model + (1|topic) + (1|review))

cat("\n=== H3 model x tier interaction (LRT) ===\n")
print(anova(m_noint, m_full))
cat("\n=== H1 model main effect (LRT, from additive model) ===\n")
print(anova(m_nomod, m_noint))
cat("\n=== tier main effect (LRT) ===\n")
print(anova(m_notier, m_noint))

cat("\n=== adjusted problematic probability (emmeans, response scale) ===\n")
emm <- emmeans(m_full, ~ model | tier, type="response")
print(emm)

cat("\n=== H1 pairwise model comparisons (Bonferroni, averaged over tier) ===\n")
emm_m <- emmeans(m_full, ~ model, type="response")
print(pairs(emm_m, adjust="bonferroni"))

cat("\n=== H2 resource gradient: ordered tier linear contrast (per model) ===\n")
m_ord <- glmer(problematic ~ model*tier_o + (1|topic) + (1|review),
               data=d, family=binomial,
               control=glmerControl(optimizer="bobyqa", optCtrl=list(maxfun=2e5)))
emm_t <- emmeans(m_ord, ~ tier_o | model)
print(contrast(emm_t, "poly", max.degree=1))   # linear trend low<mod<high

cat("\n=== H2 overall tier gradient (averaged over model) ===\n")
print(contrast(emmeans(m_ord, ~ tier_o), "poly", max.degree=1))

cat("\nDONE\n")
