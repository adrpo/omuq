# Implementation Guideline: omuq Data in SSP Packages

Status: draft 0.1, implemented by omuq-python 0.1.0
Applies to: SSP 2.0, omuq schema namespace
`http://openscaling.org/UQ1/UncertaintyQuantification`

This guideline defines how omuq (openScaling Uncertainty Quantification)
documents are stored inside SSP packages and linked to the model elements
they describe. It uses the standard SSP 2.0 metadata mechanism only. A
package produced under this guideline is a conforming SSP; tools without
omuq support can open and edit it without losing the omuq data.

The key words MUST, SHOULD, and MAY are to be interpreted as in RFC 2119.

## 1. Linking mechanism

omuq documents are linked from SSP host documents through `ssc:MetaData`
elements (SSP 2.0, section 4.5.4.1).

1. The MetaData element MUST carry `type` (the MIME type) set to
   `application/x-omuq`. Readers SHOULD also accept
   `application/x-openscaling-uq` as an alias.
2. The MetaData element SHOULD carry `kind="quality"`. Uncertainty and
   credibility information is quality-related metadata in the sense of the
   SSP specification.
3. The MetaData element SHOULD reference the omuq document by relative URI
   in its `source` attribute, resolved against the location of the host
   document inside the package (`sourceBase` absent, meaning `file`).
   Writers MUST NOT use absolute URIs. Readers MAY additionally accept
   inline `ssc:Content` carrying a `uq:UncertaintyQuantification` element.
4. Because `ssc:MetaData` is an SSP 2.0 feature, a host document that
   receives an omuq link MUST declare `version="2.0"` (or later). Writers
   MUST stamp the version when injecting into a 1.0 document. Note that
   this makes the whole host document subject to SSP 2.0 rules.

## 2. Anchors: where omuq data may attach

SSP 2.0 permits MetaData on a fixed set of carriers. This guideline
sanctions four of them. The anchor determines the scope in which names
inside the omuq document are resolved (section 3).

| # | Anchor (carrier) | Intended use | Name scope |
| - | --- | --- | --- |
| A1 | `SystemStructureDescription` root of an SSD | study of the whole (multi-)system | hierarchical names from the root system |
| A2 | `System` / `Component` / `SignalDictionaryReference` | study of one element | names relative to that element |
| A3 | `ParameterBinding` in an SSD | uncertainty of one applied parameter source | same scope as the element owning the binding |
| A4 | `ParameterSet` root of an SSV file | distribution overlay for a parameter set | parameter names declared in that SSV |

Notes.

1. Connectors and individual SSV parameters cannot carry MetaData in
   SSP 2.0. Fine-grained targeting is expressed inside the omuq document
   through names, anchored at the nearest legal carrier.
2. A4 pairs nominal values (SSV) with distributions (omuq) without
   modifying the SSV values. Writers SHOULD prefer A4 when the uncertainty
   belongs to a reusable parameter file rather than to one system.
3. SSM and SSB roots also accept MetaData in SSP 2.0. They are not
   sanctioned as omuq anchors by this version of the guideline.
4. One carrier MAY hold several MetaData elements (omuq links next to
   SRMD or other metadata). Readers MUST select by MIME type, not by
   position, and MUST ignore MetaData of unknown types.

## 3. Name resolution

Names appear in the omuq document as `UncertainParameter/@name`,
`ObservedVariable/@name`, and `CalibrationTargets/Target/@parameterName`.

1. For anchors A1 to A3, names are hierarchical SSP names relative to the
   anchor scope, using `.` as the separator, exactly as SSD parameter
   bindings resolve names. For A1 the scope is the root `System`. For A2
   and A3 the scope is the anchored element (for A3, the element that owns
   the binding).
2. For anchor A4, `UncertainParameter` and `Target` names MUST match
   parameter names declared in the host SSV. `ObservedVariable` names are
   outside the SSV and are not checked at this anchor.
3. Both SSP element names and FMI variable names may legally contain
   dots, so a dotted name can be ambiguous. Validators MUST accept any
   interpretation that resolves (see level 3 below) and tools that need a
   unique element path MUST offer tuple-based addressing.
4. The omuq `Model` element MAY be present. When the document is attached
   through an anchor, the anchor defines the subject of the study. If
   `Model/@file` is also present it SHOULD agree with the anchor
   (for A2 on a Component, with the component `source`). On conflict the
   anchor wins.

## 4. Storage conventions

1. omuq documents MUST be stored under `resources/` of the SSP package.
   The RECOMMENDED location is `resources/uq/<name>.uq.xml`. They MUST NOT
   be stored under `extra/`, because SSP allows tools to modify or drop
   `extra/` content they do not understand.
2. File names are opaque. The `source` attribute of the MetaData link is
   the only normative connection between host and document.
3. Study names (`UncertaintyQuantification/@name`) MUST be unique within
   a package. Multiple studies per package, and multiple anchors per
   study document, are allowed.
4. Two or more MetaData links MAY reference the same omuq document. A
   tool that removes the last remaining link SHOULD also remove the then
   unreferenced document from `resources/`.
5. Writers SHOULD fill the `ssc:ATopLevelMetaData` attributes on the omuq
   root (`generationTool`, `generationDateAndTime`, `author`,
   `fileversion`) when creating or modifying a document.

## 5. Injection position

`ssc:MetaData` has a fixed place in each carrier content model. Writers
MUST insert new MetaData after the last existing predecessor or MetaData
sibling and before everything else. The verified SSP 2.0 content models
are:

| Carrier | Order of children |
| --- | --- |
| `SystemStructureDescription` | `System`, `Enumerations?`, `Units?`, `DefaultExperiment?`, **`MetaData*`**, `Signature*`, `Annotations?` |
| `TElement` (System, Component, SignalDictionaryReference) | `Connectors?`, `ElementGeometry?`, `ParameterBindings?`, **`MetaData*`**, `Signature*`, then subtype children (`Elements` etc., `Annotations?`) |
| `ParameterBinding` | `ParameterValues?`, `ParameterMapping?`, **`MetaData*`**, `Signature*`, `Annotations?` |
| SSV `ParameterSet` | `Parameters`, `Enumerations?`, `Units?`, **`MetaData*`**, `Signature*`, `Annotations?` |

Editors modifying third-party host documents SHOULD make minimal edits
and preserve all other content, including comments, vendor annotations,
and formatting.

## 6. External data of the omuq document

The omuq `AExternalSource` attribute group (`source`, `type`,
`sourceBase`, `checksum`, `checksumType`) externalizes large payloads such
as experiment points or result tables.

1. Relative `source` URIs resolve against the location of the omuq
   document itself. Referenced files MUST live inside the package,
   RECOMMENDED next to the document (for example
   `resources/uq/points.csv`).
2. `sourceBase` values other than `file` are outside this guideline.
3. When `checksum` is present, `checksumType` SHOULD name the algorithm
   (`sha-256` RECOMMENDED; `sha-1`, `sha-512`, `md5` accepted). Validators
   MUST verify present checksums.

## 6a. Recording results back into a study

After a run, results are recorded into the study document that describes
the run. This section is normative for any write-back that follows the
pattern omuq-python's `UqManager.update`/`UqManager.record_result`
implement (section 9).

1. Recording results MUST modify the omuq document already linked at the
   anchor being recorded into (the same package entry, re-serialized)
   and MUST NOT create a second document for the same study. A
   study with no package entry of its own (stored inline as
   `ssc:MetaData/Content`) cannot be a write-back target.
2. `ResultsType` carries no id and no name, so a tool cannot tell from the
   document alone whether a result was already recorded. Implementations
   SHOULD therefore replace the `ResultSet` of the activity being recorded
   into on every recording rather than append to it, so that recording the
   same run twice produces identical bytes. Hand-authored results that
   must survive a recording belong in a different activity.
3. A domain-violation count MUST be written as an `ErrorMetric` with
   `type="DomainViolationCount"`, `name` set to the monitored domain's id,
   `value` set to its outside-sample count, `threshold="0.0"` (the
   attribute is float-typed, so the lexical form carries the decimal), and
   `pass` set to `true` exactly when `value` is zero; one such metric per
   monitored domain.
4. A domain fitted from a run's samples (a realized operating envelope,
   for instance) MUST be appended to the study's `Domains` element rather
   than replace a domain it is meant to be compared against; like any
   domain, its id MUST stay unique within the document (section 7, level
   2).
5. A `DomainCoverage` recorded from a run MUST set each region's
   `classification` to one of the fixed enumeration values (`Covered`,
   `HighRisk`, `AcceptableRisk`, `NotNeeded`), and its
   `requestedDomainRef`/`realizedDomainRef` MUST resolve to ids that exist
   in the document, checked the same as any other reference (section 7,
   level 2). A run that left the domain being reported on MUST NOT be
   auto-classified; classifying the excursion requires engineering
   judgment. Tools SHOULD record the sample counts the classification was
   based on in the coverage's or region's `description`.
6. A run's sample table, when externalized, follows section 6 exactly: it
   MUST be stored under `resources/uq/`, referenced by a relative `source`
   on an otherwise-empty `Results` element, and carry `checksum` with
   `checksumType="sha-256"` (RECOMMENDED) computed over the exact bytes
   stored.
7. Writers SHOULD refresh `generationDateAndTime` whenever a recording
   modifies the document, per section 4.5.

## 7. Validation levels

The omuq schema types all cross-references as plain `xs:string`, so XSD
validation alone does not check link integrity. Conforming validators
implement three cumulative levels.

**Level 1, schema.** Every omuq document validates against the omuq XSD
set. Every host document carrying an omuq link validates against the SSP
2.0 XSDs.

**Level 2, links.** MetaData `source` URIs resolve to package entries.
External sources resolve and match their checksums. In-document references
(`requiredAssumptionsRefs` as a whitespace-separated id list,
`activityDomainRef`, `domainRef`, `parentRef`, `requestedDomainRef`,
`realizedDomainRef`, `OperationalDomainRef/@ref`) point at existing ids.
Ids are unique per document. Study names are unique per package.
References containing `/` or `#` are treated as cross-file URIs: the file
part must resolve, the fragment is reported as unverified.

**Level 3, names.** Every `UncertainParameter`, `ObservedVariable`, and
calibration `Target` name resolves in the anchor scope. Against an SSD
scope, a name that reaches a declared connector is resolved. A name that
lands on a `Component` without matching a declared connector is a warning
only, because the FMU may define the variable without exposing it as a
connector. A name that reaches no element path at all is an error. At A4
anchors, parameter names not present in the host SSV are warnings.

omuq-python reports these as issue codes `L1.*`, `L2.*`, `L3.*`.

## 8. Worked example

Host `SystemStructure.ssd` after attaching a system-level study (A1). The
only changes against the input are the `version` attribute and one
MetaData element. Vendor content is untouched.

```xml
<?xml version='1.0' encoding='UTF-8'?>
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon"
    version="2.0" name="Demo">
  <ssd:System name="plant">
    <ssd:Connectors>...</ssd:Connectors>
    <ssd:ParameterBindings>
      <ssd:ParameterBinding source="resources/params.ssv"/>
    </ssd:ParameterBindings>
    <!-- vendor comment that must survive round trips -->
    <ssd:Elements>
      <ssd:Component name="battery" source="resources/battery.fmu"
          type="application/x-fmu-sharedlibrary">...</ssd:Component>
    </ssd:Elements>
  </ssd:System>
  <ssc:MetaData kind="quality" type="application/x-omuq"
      source="resources/uq/BatteryUQ.uq.xml"/>
</ssd:SystemStructureDescription>
```

The referenced document `resources/uq/BatteryUQ.uq.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<uq:UncertaintyQuantification
    xmlns:uq="http://openscaling.org/UQ1/UncertaintyQuantification"
    name="BatteryUQ" generationTool="omuq-python 0.1.0"
    generationDateAndTime="2026-08-07T12:56:50Z">
  <uq:Activities>
    <uq:ForwardUncertaintyQuantification>
      <uq:ParameterSet>
        <uq:Parameters>
          <uq:UncertainParameter name="battery.R0" source="Measured">
            <uq:Normal mu="0.05" sigma="0.005"/>
          </uq:UncertainParameter>
        </uq:Parameters>
      </uq:ParameterSet>
      <uq:ObservedVariables>
        <uq:ObservedVariable name="battery.V"/>
      </uq:ObservedVariables>
      <uq:SamplingMethod>
        <uq:LatinHyperCube numberOfSamples="100"/>
      </uq:SamplingMethod>
    </uq:ForwardUncertaintyQuantification>
  </uq:Activities>
</uq:UncertaintyQuantification>
```

The same document attached as an overlay on the SSV (A4) instead uses
`source="uq/BatteryUQ.uq.xml"` on the `ParameterSet` root of
`resources/params.ssv`, because the URI resolves relative to the SSV.

## 9. SDK API contract (omuq-python)

`SspPackage.open(path)` loads the archive and requires the mandatory
`SystemStructure.ssd` root entry. `pkg.uq.studies()` returns
`AttachedStudy(anchor, entry, source, kind, mime, document)` records for
every omuq link at any sanctioned anchor. `pkg.uq.attach(document, anchor)`
serializes the typed document to `resources/uq/`, injects the MetaData
node at the schema-correct position, stamps host version and generation
attributes, and enforces study-name uniqueness. `pkg.uq.detach(attached)`
removes the link and garbage-collects the document when it was the last
reference. `pkg.uq.validate(level=1..3)` produces the issue report defined
in section 7. `pkg.save(path)` writes unmodified entries back unchanged
and re-serializes only modified hosts.

`Simulation.from_package(package, study=0, activity=0, driver=None, ...)`
opens (or reuses) a package, resolves its attached study and activity,
takes the time grid from the most specific of an explicit argument, the
activity's `SimulationSetting`, and the SSD's `DefaultExperiment`, and,
unless `driver` is given, selects a backend with `auto_driver`.
`pkg.uq.record_result(attached, result, ...)` records a finished run's
domain-violation counts, sample count, and (optionally) its sample table
and per-variable summaries into one activity's `ResultSet`, per section 6a.
`pkg.uq.update(attached)` re-serializes an already-attached study whose
in-memory document was edited directly (a domain or coverage added, for
instance) back into its package entry. `omuq.fit_operational_domain`/
`fit_activity_domain` (`omuq.fitting`) fit a `TypedOperationalDomain`/
`ActivityDomain` boundary to a cloud of observed points (typically a
finished run's samples) for attaching or recording back into the study the
same way a hand-authored domain would be.

## 10. Open points

1. Cross-file reference syntax for the string-typed `*Ref` attributes
   (plain id versus `file#fragment`) is not fixed by the omuq schema.
   This guideline treats values containing `/` or `#` as URIs and leaves
   fragment verification open.
2. `ExperimentPoints/PointSet/@id` is typed `xs:string` while sibling ids
   use `xs:ID`. Feeding this back to the schema authors is recommended.
3. `sourceBase` values other than `file`, and omuq links on SSM or SSB
   roots, are reserved for a future revision.
