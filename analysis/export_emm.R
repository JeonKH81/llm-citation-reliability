suppressMessages({library(lme4); library(emmeans)})
d <- read.csv("refdata_main.csv", stringsAsFactors=FALSE)
d$model <- factor(d$model, levels=c("gpt","claude","gemini"))
d$tier  <- factor(d$tier, levels=c("low","moderate","high"))
m <- glmer(problematic ~ model*tier + (1|topic) + (1|review), data=d, family=binomial,
           control=glmerControl(optimizer="bobyqa", optCtrl=list(maxfun=2e5)))
emm <- as.data.frame(emmeans(m, ~ model | tier, type="response"))
write.csv(emm, "emm_main.csv", row.names=FALSE)
cat("exported emm_main.csv\n")
