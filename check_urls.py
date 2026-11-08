from django.urls import reverse
for name in ["external_analyse_quantitative", "external_analyse_quantitative_recap",
             "external_analyse_exploitation", "external_analyse_exploitation_recap",
             "external_journal_materiel"]:
    print(name, "->", reverse(name))
print("ALL IMPORTS OK")