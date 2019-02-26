#!/usr/bin/perl
use strict;
use JSON::PP;
use Data::Dumper;

# by default a module will receive one argument: a path to a temporary file containing key - value pairs,
# but we want JSON and the next line comment will let Ansible know to provide that instead.
# WANT_JSON

my %results = (failed  => JSON::PP::false, changed => JSON::PP::false, msg => 'pong');

sub fail_json {

	$results{failed} = JSON::PP::true;
	$results{msg} = $_;

	die encode_json(\%results);
}

# prep return

# open args file and parse json
open my $a, "<", $ARGV[0] or fail_json("Could not open $ARGV[0]\n");
$/ = undef;
my $json_args = <$a>;
my $options = decode_json $json_args;
close $a;

# consume options, skip internal _ansible keys
while (my ($key, $value) = each %$options) {
    if (not $key =~ /_ansible/) {
		$results{$key} = $value;
		delete %$options{$key};
	}
}

#### we would do other work here ####
# we would check options for checkmode/diff mode/etc

# return JSON formatted string
print encode_json \%results;
