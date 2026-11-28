import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_OWL = """<?xml version="1.0"?>
<rdf:RDF xmlns="http://example.org/aula#" xml:base="http://example.org/aula"
  xmlns:owl="http://www.w3.org/2002/07/owl#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:vs="http://www.w3.org/2003/06/sw-vocab-status/ns#">
  <owl:Ontology rdf:about="http://example.org/aula"/>
  <owl:Class rdf:about="#Pessoa">
    <rdfs:label>Pessoa</rdfs:label>
    <rdfs:comment>Ser humano.</rdfs:comment>
    <dcterms:source>Dicionário</dcterms:source>
    <dcterms:creator>Ana</dcterms:creator>
    <vs:term_status>stable</vs:term_status>
  </owl:Class>
  <owl:Class rdf:about="#Aluno">
    <rdfs:subClassOf rdf:resource="#Pessoa"/>
    <rdfs:label>Aluno</rdfs:label>
  </owl:Class>
  <owl:Class rdf:about="#Curso">
    <owl:disjointWith rdf:resource="#Pessoa"/>
  </owl:Class>
  <owl:ObjectProperty rdf:about="#matriculadoEm">
    <rdfs:domain>
      <owl:Class><owl:unionOf rdf:parseType="Collection">
        <owl:Class rdf:about="#Aluno"/><owl:Class rdf:about="#Pessoa"/>
      </owl:unionOf></owl:Class>
    </rdfs:domain>
    <rdfs:range rdf:resource="#Curso"/>
  </owl:ObjectProperty>
</rdf:RDF>
"""
