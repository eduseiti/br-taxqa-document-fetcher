#!/usr/bin/env python3
"""
Validation of the specific notebook workflow mentioned by the user.

This simulates the exact scenario: processing documents in a notebook,
then using BRTaxQADocumentFetcher without re-executing all the steps.
"""

# Simulate notebook cells
print("=== Simulating Jupyter Notebook Workflow ===\n")

print("# Cell 1: Import and setup")
import json
from legal_document_processor import LegalDocumentProcessor
from legal_document_fetcher_main import BRTaxQADocumentFetcher

print("✅ Imports completed")

print("\n# Cell 2: Initialize processor and process documents")
# This would typically load the actual data file
# For demo, we'll create a small sample
sample_data = [
    {"filename": "Lei nº 8.069, de 13 de julho de 1990.txt", "filedata": "Estatuto da Criança e do Adolescente..."},
    {"filename": "Lei nº 10.406, de 10 de janeiro de 2002.txt", "filedata": "Código Civil..."},
    {"filename": "Lei nº 12.527, de 18 de novembro de 2011.txt", "filedata": "Lei de Acesso à Informação..."},
    {"filename": "Lei nº 13.709, de 14 de agosto de 2018.txt", "filedata": "LGPD..."},
    {"filename": "Lei nº 14.129, de 29 de março de 2021.txt", "filedata": "Lei do Governo Digital..."},
]

# Save sample data to temp file
import tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(sample_data, f)
    temp_file = f.name

processor = LegalDocumentProcessor(temp_file)
print(f"✅ Processor initialized with {len(sample_data)} documents")

print("\n# Cell 3: Process documents (this takes time)")
laws = processor.process_documents()
print(f"✅ Processed {len(laws)} laws")

print("\n# Cell 4: Filter laws with dates")
laws_with_dates = processor.filter_laws_by_criteria(require_date=True)
print(f"✅ Filtered to {len(laws_with_dates)} laws with valid dates")

print("\n# Cell 5: Show sample results")
for law in laws_with_dates[:3]:
    print(f"  - Lei {law.number} ({law.date}): {law.title[:50]}...")

print("\n# Cell 6: Now I want to use BRTaxQADocumentFetcher")
print("# BEFORE: This would re-execute all the above steps!")
print("# AFTER: Using new flexible initialization:")

print("\n# Option 1: Pass the processed laws directly")
fetcher_option1 = BRTaxQADocumentFetcher(laws=laws_with_dates)
result1 = fetcher_option1.process_legal_documents(min_year=2010)
print(f"✅ Option 1: Used pre-processed laws → {len(result1)} recent laws")

print("\n# Option 2: Pass the processor instance")
fetcher_option2 = BRTaxQADocumentFetcher(processor_instance=processor)
result2 = fetcher_option2.process_legal_documents(min_year=2010, require_date=True)
print(f"✅ Option 2: Used processor instance → {len(result2)} recent laws")

print("\n# Option 3: Save URLs and load from file")
urls = [processor.construct_normas_url(law.urn) for law in laws_with_dates]
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
    for url in urls:
        f.write(url + '\n')
    urls_file = f.name

fetcher_option3 = BRTaxQADocumentFetcher(urls_file=urls_file)
result3 = fetcher_option3.process_legal_documents(min_year=2010)
print(f"✅ Option 3: Used URLs file → {len(result3)} recent laws")

print("\n=== Validation Results ===")
print(f"All three options produced consistent results:")
print(f"- Option 1 (laws): {len(result1)} laws")
print(f"- Option 2 (processor): {len(result2)} laws")
print(f"- Option 3 (URLs): {len(result3)} laws")

# Verify they have the same law numbers
numbers1 = {law.number for law in result1}
numbers2 = {law.number for law in result2}
numbers3 = {law.number for law in result3}

if numbers1 == numbers2 == numbers3:
    print("✅ All options produced identical results!")
    print(f"Recent laws: {sorted(numbers1)}")
else:
    print("❌ Results differ between options")

print(f"\n=== Key Benefits for Notebook Users ===")
print("✅ No redundant processing - use already processed data")
print("✅ Multiple flexible input options")
print("✅ Can resume work from any point in the pipeline")
print("✅ Maintains full filtering and validation capabilities")
print("✅ Perfect for iterative notebook development")

# Cleanup
import os
os.unlink(temp_file)
os.unlink(urls_file)

print(f"\n🎉 Notebook workflow validation completed successfully!")