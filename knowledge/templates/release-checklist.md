# Release checklist: <target package>

- [ ] Package metadata: name, description ("<target language> port of <upstream> <version>"), license
      (compatible with upstream), repository, keywords.
- [ ] Version policy relative to upstream: <mirror upstream x.y and add a port patch number, or semver of its own>.
- [ ] README section "Parity with upstream" generated from `.porter/PARITY.md`, with the evidence date.
- [ ] Attribution: upstream copyright and license notice kept where the license requires it.
- [ ] CHANGELOG entry for the first release.
- [ ] CI green on the supported runtime versions.
- [ ] Publish command for the ecosystem: <npm publish / twine upload / cargo publish / go tag / mvn deploy>.
- [ ] Divergences listed in the README, each with a one-line rationale.
