import unittest
import spack.spec
from spack.spec import *
from spack.parse import Token, ParseError

# Sample output for a complex lexing.
complex_lex = [Token(ID, 'mvapich_foo'),
               Token(DEP),
               Token(ID, '_openmpi'),
               Token(AT),
               Token(ID, '1.2'),
               Token(COLON),
               Token(ID, '1.4'),
               Token(COMMA),
               Token(ID, '1.6'),
               Token(PCT),
               Token(ID, 'intel'),
               Token(AT),
               Token(ID, '12.1'),
               Token(COLON),
               Token(ID, '12.6'),
               Token(ON),
               Token(ID, 'debug'),
               Token(OFF),
               Token(ID, 'qt_4'),
               Token(DEP),
               Token(ID, 'stackwalker'),
               Token(AT),
               Token(ID, '8.1_1e')]


class SpecTest(unittest.TestCase):
    # ================================================================================
    # Parse checks
    # ================================================================================
    def check_parse(self, expected, spec=None):
        """Assert that the provided spec is able to be parsed.
           If this is called with one argument, it assumes that the string is
           canonical (i.e., no spaces and ~ instead of - for variants) and that it
           will convert back to the string it came from.

           If this is called with two arguments, the first argument is the expected
           canonical form and the second is a non-canonical input to be parsed.
        """
        if spec == None:
            spec = expected
        output = spack.spec.parse(spec)
        parsed = (" ".join(str(spec) for spec in output))
        self.assertEqual(expected, parsed)


    def check_lex(self, tokens, spec):
        """Check that the provided spec parses to the provided list of tokens."""
        lex_output = SpecLexer().lex(spec)
        for tok, spec_tok in zip(tokens, lex_output):
            if tok.type == ID:
                self.assertEqual(tok, spec_tok)
            else:
                # Only check the type for non-identifiers.
                self.assertEqual(tok.type, spec_tok.type)


    def check_satisfies(self, lspec, rspec):
        l, r = Spec(lspec), Spec(rspec)
        self.assertTrue(l.satisfies(r))
        self.assertTrue(r.satisfies(l))

        try:
            l.constrain(r)
            r.constrain(l)
        except SpecError, e:
            self.fail("Got a SpecError in constrain!", e.message)


    def assert_unsatisfiable(lspec, rspec):
        l, r = Spec(lspec), Spec(rspec)
        self.assertFalse(l.satisfies(r))
        self.assertFalse(r.satisfies(l))

        self.assertRaises(l.constrain, r)
        self.assertRaises(r.constrain, l)


    def check_constrain(self, expected, constrained, constraint):
        exp = Spec(expected)
        constrained = Spec(constrained)
        constraint = Spec(constraint)
        constrained.constrain(constraint)
        self.assertEqual(exp, constrained)


    def check_invalid_constraint(self, constrained, constraint):
        constrained = Spec(constrained)
        constraint = Spec(constraint)
        self.assertRaises(UnsatisfiableSpecError, constrained.constrain, constraint)


    # ================================================================================
    # Parse checks
    # ===============================================================================
    def test_package_names(self):
        self.check_parse("mvapich")
        self.check_parse("mvapich_foo")
        self.check_parse("_mvapich_foo")

    def test_simple_dependence(self):
        self.check_parse("openmpi^hwloc")
        self.check_parse("openmpi^hwloc^libunwind")

    def test_dependencies_with_versions(self):
        self.check_parse("openmpi^hwloc@1.2e6")
        self.check_parse("openmpi^hwloc@1.2e6:")
        self.check_parse("openmpi^hwloc@:1.4b7-rc3")
        self.check_parse("openmpi^hwloc@1.2e6:1.4b7-rc3")

    def test_full_specs(self):
        self.check_parse("mvapich_foo^_openmpi@1.2:1.4,1.6%intel@12.1+debug~qt_4^stackwalker@8.1_1e")

    def test_canonicalize(self):
        self.check_parse(
            "mvapich_foo^_openmpi@1.2:1.4,1.6%intel@12.1:12.6+debug~qt_4^stackwalker@8.1_1e",
            "mvapich_foo ^_openmpi@1.6,1.2:1.4%intel@12.1:12.6+debug~qt_4 ^stackwalker@8.1_1e")

        self.check_parse(
            "mvapich_foo^_openmpi@1.2:1.4,1.6%intel@12.1:12.6+debug~qt_4^stackwalker@8.1_1e",
            "mvapich_foo ^stackwalker@8.1_1e ^_openmpi@1.6,1.2:1.4%intel@12.1:12.6~qt_4+debug")

        self.check_parse(
            "x^y@1,2:3,4%intel@1,2,3,4+a~b+c~d+e~f",
            "x ^y~f+e~d+c~b+a@4,2:3,1%intel@4,3,2,1")

        self.check_parse("x^y", "x@: ^y@:")

    def test_parse_errors(self):
        self.assertRaises(ParseError, self.check_parse, "x@@1.2")
        self.assertRaises(ParseError, self.check_parse, "x ^y@@1.2")
        self.assertRaises(ParseError, self.check_parse, "x@1.2::")
        self.assertRaises(ParseError, self.check_parse, "x::")

    def test_duplicate_variant(self):
        self.assertRaises(DuplicateVariantError, self.check_parse, "x@1.2+debug+debug")
        self.assertRaises(DuplicateVariantError, self.check_parse, "x ^y@1.2+debug+debug")

    def test_duplicate_depdendence(self):
        self.assertRaises(DuplicateDependencyError, self.check_parse, "x ^y ^y")

    def test_duplicate_compiler(self):
        self.assertRaises(DuplicateCompilerError, self.check_parse, "x%intel%intel")
        self.assertRaises(DuplicateCompilerError, self.check_parse, "x%intel%gcc")
        self.assertRaises(DuplicateCompilerError, self.check_parse, "x%gcc%intel")
        self.assertRaises(DuplicateCompilerError, self.check_parse, "x ^y%intel%intel")
        self.assertRaises(DuplicateCompilerError, self.check_parse, "x ^y%intel%gcc")
        self.assertRaises(DuplicateCompilerError, self.check_parse, "x ^y%gcc%intel")


    # ================================================================================
    # Satisfiability and constraints
    # ================================================================================
    def test_satisfies(self):
        self.check_satisfies('libelf@0.8.13', 'libelf@0:1')
        self.check_satisfies('libdwarf^libelf@0.8.13', 'libdwarf^libelf@0:1')


    def test_constrain(self):
        self.check_constrain('libelf@2.1:2.5', 'libelf@0:2.5', 'libelf@2.1:3')
        self.check_constrain('libelf@2.1:2.5%gcc@4.5:4.6',
                             'libelf@0:2.5%gcc@2:4.6', 'libelf@2.1:3%gcc@4.5:4.7')

        self.check_constrain('libelf+debug+foo', 'libelf+debug', 'libelf+foo')
        self.check_constrain('libelf+debug+foo', 'libelf+debug', 'libelf+debug+foo')

        self.check_constrain('libelf+debug~foo', 'libelf+debug', 'libelf~foo')
        self.check_constrain('libelf+debug~foo', 'libelf+debug', 'libelf+debug~foo')

        self.check_constrain('libelf=bgqos_0', 'libelf=bgqos_0', 'libelf=bgqos_0')
        self.check_constrain('libelf=bgqos_0', 'libelf', 'libelf=bgqos_0')


    def test_invalid_constraint(self):
        self.check_invalid_constraint('libelf@0:2.0', 'libelf@2.1:3')
        self.check_invalid_constraint('libelf@0:2.5%gcc@4.8:4.9', 'libelf@2.1:3%gcc@4.5:4.7')

        self.check_invalid_constraint('libelf+debug', 'libelf~debug')
        self.check_invalid_constraint('libelf+debug~foo', 'libelf+debug+foo')

        self.check_invalid_constraint('libelf=bgqos_0', 'libelf=x86_54')


    # ================================================================================
    # Lex checks
    # ================================================================================
    def test_ambiguous(self):
        # This first one is ambiguous because - can be in an identifier AND
        # indicate disabling an option.
        self.assertRaises(
            AssertionError, self.check_lex, complex_lex,
            "mvapich_foo^_openmpi@1.2:1.4,1.6%intel@12.1:12.6+debug-qt_4^stackwalker@8.1_1e")

    # The following lexes are non-ambiguous (add a space before -qt_4) and should all
    # result in the tokens in complex_lex
    def test_minimal_spaces(self):
        self.check_lex(
            complex_lex,
            "mvapich_foo^_openmpi@1.2:1.4,1.6%intel@12.1:12.6+debug -qt_4^stackwalker@8.1_1e")
        self.check_lex(
            complex_lex,
            "mvapich_foo^_openmpi@1.2:1.4,1.6%intel@12.1:12.6+debug~qt_4^stackwalker@8.1_1e")

    def test_spaces_between_dependences(self):
        self.check_lex(
            complex_lex,
            "mvapich_foo ^_openmpi@1.2:1.4,1.6%intel@12.1:12.6+debug -qt_4 ^stackwalker @ 8.1_1e")
        self.check_lex(
            complex_lex,
            "mvapich_foo ^_openmpi@1.2:1.4,1.6%intel@12.1:12.6+debug~qt_4 ^stackwalker @ 8.1_1e")

    def test_spaces_between_options(self):
        self.check_lex(
            complex_lex,
            "mvapich_foo ^_openmpi @1.2:1.4,1.6 %intel @12.1:12.6 +debug -qt_4 ^stackwalker @8.1_1e")

    def test_way_too_many_spaces(self):
        self.check_lex(
            complex_lex,
            "mvapich_foo ^ _openmpi @ 1.2 : 1.4 , 1.6 % intel @ 12.1 : 12.6 + debug - qt_4 ^ stackwalker @ 8.1_1e")