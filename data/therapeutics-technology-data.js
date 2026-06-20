/*
 * Static-compatible content store for the GeneDr therapeutics program.
 * Future automation: a scheduled build can normalize openFDA Drugs@FDA data or
 * FDA RSS/API output into the shapes below, validate it, and replace the arrays.
 * Keep this file as the reviewed fallback so the GitHub Pages site still works
 * when an upstream service is unavailable. Clinical review is required before publish.
 */
window.GeneDrTherapeuticsData = {
  featuredPeriod: "June 2026",
  monthlyFeaturedPicks: [
    { product: "Otarmeni", company: "Regeneron Pharmaceuticals", indication: "OTOF-related severe-to-profound sensorineural hearing loss", type: "Dual-AAV gene therapy", explanation: "The first FDA-approved gene therapy for genetic hearing loss, granted accelerated approval in April 2026.", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-first-ever-gene-therapy-treatment-genetic-hearing-loss-under-national-priority-voucher" },
    { product: "Kresladi", company: "Rocket Pharmaceuticals", indication: "Severe leukocyte adhesion deficiency type I", type: "Ex vivo stem-cell gene therapy", explanation: "An accelerated-approval therapy that introduces functional ITGB2 copies into a patient's own blood stem cells.", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-first-gene-therapy-severe-leukocyte-adhesion-deficiency-type-i" },
    { product: "Itvisma", company: "Novartis Gene Therapies", indication: "Spinal muscular atrophy in patients age 2 years and older", type: "Intrathecal AAV gene therapy", explanation: "A gene therapy approved in November 2025 for adult and pediatric patients with a confirmed SMN1 mutation.", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-gene-therapy-treatment-spinal-muscular-atrophy" }
  ],

  therapeuticsData: [
    { category: "Lysosomal Storage Disorders", columns: ["Disease", "Gene", "ERT", "SRT / Chaperone", "Gene Therapy", "Other"], rows: [
      ["Gaucher Disease", "GBA1", "Cerezyme (Sanofi); Vpriv (Takeda)", "Cerdelga (Sanofi)", "Clinical trials", "Substrate reduction and supportive care"],
      ["Fabry Disease", "GLA", "Fabrazyme (Sanofi)", "Galafold (Amicus Therapeutics)", "Clinical trials", "Variant-specific eligibility applies"],
      ["Pompe Disease", "GAA", "Lumizyme (Sanofi); Nexviazyme (Sanofi)", "No approved therapy", "Clinical trials", "Immune tolerance may be considered"],
      ["MPS I", "IDUA", "Aldurazyme (BioMarin/Sanofi)", "No approved therapy", "Clinical trials", "Hematopoietic stem cell transplant"],
      ["MPS II", "IDS", "Elaprase (Takeda)", "No approved therapy", "Clinical trials", "Supportive multidisciplinary care"],
      ["MPS III", "SGSH, NAGLU, HGSNAT, GNS", "No approved therapy", "No approved therapy", "Clinical trials", "Supportive multidisciplinary care"],
      ["MPS IVA", "GALNS", "Vimizim (BioMarin)", "No approved therapy", "Clinical trials", "Orthopedic and respiratory care"],
      ["MPS VI", "ARSB", "Naglazyme (BioMarin)", "No approved therapy", "Clinical trials", "Supportive multidisciplinary care"],
      ["Alpha-Mannosidosis", "MAN2B1", "Lamzede (Chiesi Global Rare Diseases)", "No approved therapy", "Clinical trials", "Supportive multidisciplinary care"],
      ["CLN2 Disease", "TPP1", "Brineura (BioMarin)", "No approved therapy", "Clinical trials", "Seizure and supportive care"]
    ]},
    { category: "Skeletal Dysplasia", columns: ["Disease", "Gene", "Targeted Therapy", "Gene Therapy", "Other"], rows: [
      ["Achondroplasia", "FGFR3", "Voxzogo (BioMarin); Yuviwel / TransCon CNP (Ascendis Pharma)", "Preclinical research", "Limb and symptom management"],
      ["Hypochondroplasia", "FGFR3", "Clinical trials", "Preclinical research", "Supportive care"],
      ["Hypophosphatasia", "ALPL", "Strensiq (Alexion/AstraZeneca)", "Clinical trials", "Dental and orthopedic care"],
      ["Osteogenesis Imperfecta", "Multiple genes", "Clinical trials", "Preclinical research", "Bisphosphonates and fracture prevention"],
      ["X-linked Hypophosphatemia", "PHEX", "Crysvita (Ultragenyx/Kyowa Kirin)", "Preclinical research", "Phosphate and active vitamin D"]
    ]},
    { category: "Neuromuscular Disorders", columns: ["Disease", "Gene", "Targeted Therapy", "Gene Therapy", "Other"], rows: [
      ["SMA", "SMN1", "Spinraza (Biogen); Evrysdi (Roche)", "Zolgensma (Novartis)", "Respiratory, nutrition, and rehabilitation care"],
      ["Duchenne Muscular Dystrophy", "DMD", "Exondys 51 (Sarepta Therapeutics); Viltepso (NS Pharma)", "Elevidys (Sarepta Therapeutics)", "Corticosteroids and cardiac care"],
      ["Becker Muscular Dystrophy", "DMD", "Clinical trials", "Clinical trials", "Cardiac and rehabilitation care"],
      ["Myotubular Myopathy", "MTM1", "Clinical trials", "Clinical trials", "Respiratory and supportive care"],
      ["Limb Girdle Muscular Dystrophy", "Multiple genes", "Clinical trials", "Clinical trials", "Subtype-specific supportive care"]
    ]},
    { category: "Inherited Retinal Disorders", columns: ["Disease", "Gene", "Targeted Therapy", "Gene Therapy", "Other"], rows: [
      ["RPE65 Retinal Dystrophy", "RPE65", "No approved pharmacologic therapy", "Luxturna (Spark Therapeutics/Roche)", "Low-vision services"],
      ["Choroideremia", "CHM", "Clinical trials", "Clinical trials", "Low-vision services"],
      ["RPGR Retinitis Pigmentosa", "RPGR", "Clinical trials", "Clinical trials", "Low-vision services"],
      ["Stargardt Disease", "ABCA4", "Clinical trials", "Clinical trials", "Low-vision services"]
    ]},
    { category: "Hematologic Genetic Disorders", columns: ["Disease", "Gene", "Targeted Therapy", "Gene Therapy", "Other"], rows: [
      ["Sickle Cell Disease", "HBB", "Oxbryta (Pfizer; withdrawn from market); Adakveo (Novartis)", "Casgevy (Vertex Pharmaceuticals/CRISPR Therapeutics); Lyfgenia (bluebird bio)", "Hydroxyurea and transplant"],
      ["Beta-Thalassemia", "HBB", "Reblozyl (Bristol Myers Squibb)", "Zynteglo (bluebird bio); Casgevy (Vertex Pharmaceuticals/CRISPR Therapeutics)", "Transfusion, chelation, and transplant"]
    ]},
    { category: "Leukodystrophies & Neurogenetic Disorders", columns: ["Disease", "Gene", "Targeted Therapy", "Gene Therapy", "Other"], rows: [
      ["Metachromatic Leukodystrophy", "ARSA", "No approved pharmacologic therapy", "Lenmeldy (Orchard Therapeutics)", "Transplant in selected patients"],
      ["Cerebral Adrenoleukodystrophy", "ABCD1", "No approved pharmacologic therapy", "Skysona (bluebird bio)", "Transplant and endocrine care"],
      ["AADC Deficiency", "DDC", "Symptom-directed therapy", "Kebilidi (PTC Therapeutics)", "Multidisciplinary supportive care"]
    ]},
    { category: "Inborn Errors of Metabolism", columns: ["Disease", "Gene", "Targeted Therapy", "Gene Therapy", "Other"], rows: [
      ["PKU", "PAH", "Kuvan (BioMarin); Palynziq (BioMarin)", "Clinical trials", "Phenylalanine-restricted diet"],
      ["Tyrosinemia Type I", "FAH", "Orfadin (Sobi)", "Preclinical research", "Tyrosine/phenylalanine-restricted diet"],
      ["Urea Cycle Disorders", "Multiple genes", "Ravicti (Horizon/Amgen); Buphenyl (Horizon/Amgen)", "Clinical trials", "Dietary and emergency management"],
      ["MSUD", "BCKDHA, BCKDHB, DBT", "No approved disease-specific therapy", "Clinical trials", "Branched-chain amino acid restriction; transplant"],
      ["Homocystinuria", "CBS and others", "Cystadane (Recordati Rare Diseases)", "Preclinical research", "Diet and vitamin/cofactor therapy"],
      ["Methylmalonic Acidemia", "MUT and others", "Carglumic Acid (Recordati Rare Diseases) for hyperammonemia", "Clinical trials", "Diet, cofactors, and transplant evaluation"]
    ]},
    { category: "Monogenic and Syndromic Obesity", columns: ["Disease", "Gene", "Targeted Therapy", "Gene Therapy", "Other"], rows: [
      ["POMC Deficiency", "POMC", "Imcivree (Rhythm Pharmaceuticals)", "Clinical trials", "Lifestyle management"],
      ["LEPR Deficiency", "LEPR", "Imcivree (Rhythm Pharmaceuticals)", "Clinical trials", "Lifestyle management"],
      ["PCSK1 Deficiency", "PCSK1", "Imcivree (Rhythm Pharmaceuticals)", "Clinical trials", "Lifestyle management"],
      ["Bardet-Biedl Syndrome", "Multiple genes", "Imcivree (Rhythm Pharmaceuticals)", "Clinical trials", "Supportive care"],
      ["Alstrom Syndrome", "ALMS1", "Clinical trials", "Clinical trials", "Supportive care"],
      ["Prader-Willi Syndrome", "15q11-q13", "Emerging therapies", "Clinical trials", "Multidisciplinary care"]
    ]}
  ],

  companyList: [
    { name: "Sanofi", area: "Lysosomal storage disorders and rare metabolic disease", products: "Cerezyme; Cerdelga; Fabrazyme; Lumizyme; Nexviazyme; Aldurazyme", pipeline: "Next-generation enzyme replacement, substrate reduction, and genetic-medicine programs for lysosomal storage and other rare disorders.", intro: "A global biopharmaceutical company with a longstanding rare-disease portfolio spanning Gaucher, Fabry, Pompe, and MPS I.", url: "https://www.sanofi.com/" },
    { name: "Ultragenyx", area: "Rare and ultrarare genetic disease", products: "Crysvita; Mepsevii; Dojolvi", intro: "Develops biologics, small molecules, gene therapies, and nucleic-acid therapies for serious rare genetic disorders.", url: "https://www.ultragenyx.com/" },
    { name: "Takeda", area: "Lysosomal storage disorders, hematology, and immunology", products: "Vpriv; Elaprase", pipeline: "Programs across rare hematology, hereditary angioedema, immune deficiency, neuroscience, and lysosomal storage disorders.", intro: "A global biopharmaceutical company with rare-disease programs in metabolic, lysosomal, hematologic, and immune disorders.", url: "https://www.takeda.com/science/areas-of-focus/rare-diseases/" },
    { name: "BioMarin", area: "Skeletal dysplasia and inherited metabolic disease", products: "Voxzogo; Aldurazyme; Vimizim; Naglazyme; Brineura", pipeline: "Clinical and research programs in skeletal dysplasia, neuromuscular disease, and inherited metabolic disorders.", intro: "Develops therapies for serious inherited and rare disorders.", url: "https://www.biomarin.com/" },
    { name: "Ascendis Pharma", area: "Endocrinology and skeletal dysplasia", products: "Yuviwel (developed as TransCon CNP); Skytrofa; Yorvipath", pipeline: "TransCon-based programs in achondroplasia, endocrinology, and additional therapeutic areas.", intro: "Applies its TransCon platform to create potentially best-in-class therapies.", url: "https://ascendispharma.com/" },
    { name: "Alexion, AstraZeneca Rare Disease", area: "Rare metabolic, hematologic, renal, and complement-mediated disease", products: "Strensiq", intro: "The AstraZeneca rare-disease group develops therapies for severe and often life-threatening rare conditions.", url: "https://alexion.com/" },
    { name: "Biogen", area: "Neuromuscular and neurologic disease", products: "Spinraza", pipeline: "RNA-targeted and other programs for neuromuscular, neurodegenerative, and genetically defined neurologic disorders.", intro: "Develops medicines for neurological and related disorders.", url: "https://www.biogen.com/" },
    { name: "Sarepta Therapeutics", area: "Precision genetic medicine for neuromuscular disease", products: "Exondys 51; Elevidys", pipeline: "RNA-targeted therapies and gene-therapy programs for Duchenne and limb-girdle muscular dystrophies.", intro: "Develops RNA-targeted and gene therapies, with a major focus on Duchenne muscular dystrophy.", url: "https://www.sarepta.com/" },
    { name: "Vertex Pharmaceuticals and CRISPR Therapeutics", area: "Gene editing for hemoglobinopathies", products: "Casgevy", intro: "Collaborated to develop the first FDA-approved CRISPR/Cas9 gene-edited cell therapy.", url: "https://www.vrtx.com/" },
    { name: "bluebird bio", area: "Ex vivo gene therapy for severe genetic disease", products: "Zynteglo; Lyfgenia; Skysona", intro: "Develops lentiviral vector gene therapies for beta-thalassemia, sickle cell disease, and cerebral adrenoleukodystrophy.", url: "https://www.bluebirdbio.com/" },
    { name: "PTC Therapeutics", area: "Rare neurologic and metabolic disease", products: "Kebilidi", intro: "Develops differentiated therapies for rare disorders, including gene therapy for AADC deficiency.", url: "https://www.ptcbio.com/" },
    { name: "Orchard Therapeutics", area: "Hematopoietic stem-cell gene therapy", products: "Lenmeldy", intro: "A Kyowa Kirin company focused on ex vivo stem-cell gene therapies for severe inherited disorders.", url: "https://www.orchard-tx.com/" },
    { name: "Kyowa Kirin", area: "Rare metabolic and endocrine disease", products: "Crysvita, in partnership with Ultragenyx", intro: "A global specialty pharmaceutical company developing therapies across rare and underserved diseases.", url: "https://www.kyowakirin.com/" },
    { name: "Roche", area: "Neurology, ophthalmology, and precision medicine", products: "Evrysdi; Luxturna through Spark Therapeutics", pipeline: "Programs spanning genetic neurology, inherited retinal disease, RNA-targeted medicines, and gene therapy.", intro: "Develops diagnostics and medicines across major disease areas.", url: "https://www.roche.com/" },
    { name: "Spark Therapeutics", area: "AAV gene therapy for inherited disease", products: "Luxturna", intro: "A Roche company focused on gene therapies for inherited retinal and other genetic disorders.", url: "https://sparktx.com/" },
    { name: "Novartis", area: "Gene therapy and rare neurologic disease", products: "Zolgensma; Adakveo", pipeline: "AAV gene therapy, RNA-based medicines, and targeted programs for neurologic and hematologic genetic disorders.", intro: "Develops medicines and gene therapies across specialty care.", url: "https://www.novartis.com/" },
    { name: "Rhythm Pharmaceuticals", area: "Rare genetic diseases of obesity", products: "Imcivree", intro: "Focuses on therapies for hyperphagia and severe obesity caused by rare MC4R-pathway diseases.", url: "https://www.rhythmtx.com/" },
    { name: "Amicus Therapeutics", area: "Rare metabolic disease", products: "Galafold; Pombiliti plus Opfolda", pipeline: "Next-generation and combination approaches for Fabry, Pompe, and other lysosomal storage disorders.", intro: "Develops medicines for people living with rare diseases.", url: "https://www.amicusrx.com/" },
    { name: "Chiesi Global Rare Diseases", area: "Rare metabolic and lysosomal disorders", products: "Lamzede", pipeline: "Programs in lysosomal storage, metabolic, hematologic, and other high-unmet-need rare disorders.", intro: "The Chiesi business unit dedicated to therapies and support for rare diseases.", url: "https://www.chiesiglobalrarediseases.com/" },
    { name: "Recordati Rare Diseases", area: "Inherited metabolic and endocrine disorders", products: "Cystadane; Carglumic Acid", intro: "Develops and commercializes therapies for rare metabolic and endocrine conditions.", url: "https://recordatirarediseases.com/" },
    { name: "Sobi", area: "Rare hematology, immunology, and metabolic disease", products: "Orfadin", intro: "A global biopharmaceutical company dedicated to specialized treatments for rare and debilitating diseases.", url: "https://www.sobi.com/" },
    { name: "Amgen and Horizon Therapeutics", area: "Rare autoimmune, inflammatory, and metabolic disease", products: "Ravicti; Buphenyl", intro: "Horizon is part of Amgen, extending its portfolio of medicines for serious rare diseases.", url: "https://www.amgen.com/" },
    { name: "Bristol Myers Squibb", area: "Hematology and immune-mediated disease", products: "Reblozyl", intro: "A global biopharmaceutical company with therapies across hematology, oncology, immunology, and cardiovascular disease.", url: "https://www.bms.com/" },
    { name: "NS Pharma", area: "Rare neuromuscular disease", products: "Viltepso", intro: "Develops exon-skipping and other therapies for Duchenne muscular dystrophy and rare diseases.", url: "https://www.nspharma.com/" },
    { name: "Pfizer", area: "Rare hematology, cardiology, and genetic disease", products: "Oxbryta (withdrawn from market)", intro: "A global biopharmaceutical company with research and commercial programs across multiple rare-disease areas.", url: "https://www.pfizer.com/science/focus-areas/rare-disease" },
    { name: "Regeneron Pharmaceuticals", area: "Genetic medicine, immunology, and ophthalmology", products: "Otarmeni", intro: "Develops biologic and genetic medicines, including gene therapy for OTOF-related hearing loss.", url: "https://www.regeneron.com/" },
    { name: "Rocket Pharmaceuticals", area: "Gene therapy for rare pediatric disorders", products: "Kresladi", intro: "Develops lentiviral and AAV gene therapies for severe inherited diseases.", url: "https://www.rocketpharma.com/" },
    { name: "Mirum Pharmaceuticals", area: "Rare liver and metabolic disease", products: "Ctexli", intro: "Develops therapies for rare diseases affecting children and adults, with a focus on hepatology.", url: "https://mirumpharma.com/" },
    { name: "Fondazione Telethon", area: "Nonprofit research and gene therapy development", products: "Waskyra", intro: "An Italian biomedical charity supporting research and development for rare genetic diseases.", url: "https://www.telethon.it/en/" }
  ],

  fdaLastReviewed: "Static fallback reviewed June 2026",
  fdaApprovedTherapies: [
    { product: "Yuviwel", company: "Ascendis Pharma", indication: "Achondroplasia in children age 2 years and older with open growth plates", gene: "FGFR3", type: "Long-acting CNP prodrug", approval: "February 27, 2026", url: "https://investors.ascendispharma.com/news-releases/news-release-details/fda-approves-once-weekly-yuviwelr-navepegritide-children" },
    { product: "Otarmeni", company: "Regeneron Pharmaceuticals", indication: "OTOF-related severe-to-profound sensorineural hearing loss", gene: "OTOF", type: "Dual-AAV gene therapy", approval: "April 23, 2026", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-first-ever-gene-therapy-treatment-genetic-hearing-loss-under-national-priority-voucher" },
    { product: "Kresladi", company: "Rocket Pharmaceuticals", indication: "Severe leukocyte adhesion deficiency type I without an available HLA-matched sibling donor", gene: "ITGB2", type: "Ex vivo stem-cell gene therapy", approval: "March 26, 2026", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-first-gene-therapy-severe-leukocyte-adhesion-deficiency-type-i" },
    { product: "Waskyra", company: "Fondazione Telethon ETS", indication: "Wiskott-Aldrich syndrome when transplant is appropriate and no suitable matched related donor is available", gene: "WAS", type: "Ex vivo stem-cell gene therapy", approval: "December 9, 2025", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-first-gene-therapy-treatment-wiskott-aldrich-syndrome" },
    { product: "Itvisma", company: "Novartis Gene Therapies", indication: "Spinal muscular atrophy in patients age 2 years and older", gene: "SMN1", type: "Intrathecal AAV gene therapy", approval: "November 24, 2025", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-gene-therapy-treatment-spinal-muscular-atrophy" },
    { product: "Ctexli", company: "Mirum Pharmaceuticals", indication: "Cerebrotendinous xanthomatosis in adults", gene: "CYP27A1", type: "Bile acid replacement", approval: "February 21, 2025", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-first-treatment-cerebrotendinous-xanthomatosis-rare-lipid-storage-disease" },
    { product: "Voxzogo", company: "BioMarin", indication: "Achondroplasia in children with open growth plates", gene: "FGFR3", type: "CNP analog", approval: "November 19, 2021", url: "https://www.fda.gov/drugs/news-events-human-drugs/fda-approves-first-drug-improve-growth-children-most-common-form-dwarfism" },
    { product: "Zolgensma", company: "Novartis", indication: "Spinal muscular atrophy in patients under 2 years", gene: "SMN1", type: "AAV gene replacement", approval: "May 24, 2019", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-innovative-gene-therapy-treat-pediatric-patients-spinal-muscular-atrophy-rare-disease" },
    { product: "Luxturna", company: "Spark Therapeutics/Roche", indication: "Biallelic RPE65 mutation-associated retinal dystrophy", gene: "RPE65", type: "AAV gene replacement", approval: "December 19, 2017", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-novel-gene-therapy-treat-patients-rare-form-inherited-vision-loss" },
    { product: "Casgevy", company: "Vertex Pharmaceuticals/CRISPR Therapeutics", indication: "Sickle cell disease; transfusion-dependent beta-thalassemia", gene: "BCL11A enhancer / HBB pathway", type: "Ex vivo CRISPR gene editing", approval: "December 8, 2023; January 16, 2024", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-first-gene-therapies-treat-patients-sickle-cell-disease" },
    { product: "Lenmeldy", company: "Orchard Therapeutics", indication: "Presymptomatic or early symptomatic metachromatic leukodystrophy", gene: "ARSA", type: "Ex vivo stem-cell gene therapy", approval: "March 18, 2024", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-first-gene-therapy-children-metachromatic-leukodystrophy" },
    { product: "Kebilidi", company: "PTC Therapeutics", indication: "AADC deficiency", gene: "DDC", type: "AAV gene therapy", approval: "November 13, 2024", url: "https://www.fda.gov/news-events/press-announcements/fda-approves-gene-therapy-treatment-aadc-deficiency" }
  ],

  technologyLabs: [
    { name: "GeneDx", focus: "Rare disease and hereditary disorder testing", platform: "Exome, genome, and targeted sequencing", intro: "Clinical genetic testing with phenotype-informed interpretation across pediatric and adult rare disease.", url: "https://www.genedx.com/" },
    { name: "Invitae", focus: "Hereditary disease testing", platform: "Next-generation sequencing panels and exome testing", intro: "Clinical testing across hereditary cancer, cardiology, neurology, pediatrics, and reproductive health.", url: "https://www.invitae.com/" },
    { name: "PreventionGenetics", focus: "Rare and inherited disorders", platform: "Genome, exome, panels, and biochemical testing", intro: "A clinical laboratory offering broad genetic test options and custom family testing.", url: "https://www.preventiongenetics.com/" },
    { name: "Baylor Genetics", focus: "Rare disease, cytogenetics, and biochemical genetics", platform: "Genome, exome, microarray, and multi-omics", intro: "A clinical diagnostics laboratory integrating genomic and biochemical approaches.", url: "https://www.baylorgenetics.com/" },
    { name: "Variantyx", focus: "Rare disease and reproductive genetics", platform: "Whole-genome sequencing", intro: "Genome-first testing designed to detect multiple variant classes in a unified workflow.", url: "https://www.variantyx.com/" },
    { name: "Pacific Biosciences", focus: "Research and translational genomics", platform: "HiFi long-read sequencing", intro: "Sequencing technology for high-accuracy long reads, repeat expansions, phasing, and structural variation.", url: "https://www.pacb.com/" }
  ],

  industryConnectionInfo: { recipient: "info@genedrnetwork.org", subject: "Featured product consideration" }
};
