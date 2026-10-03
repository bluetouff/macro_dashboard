"""Guard the GitPython boundary fixed by GHSA-59cr-6r3x-644w.

These isolated component tests never clone a repository or contact a remote.
They do not assert that the dashboard exposes a submodule-update entry point.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from git import Repo, Submodule
from streamlit.git_util import GitRepo


class GitPythonSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = Repo.init(self.root / 'parent')
        self.addCleanup(self.repo.close)

    def submodule(self, path: str) -> Submodule:
        return Submodule(
            self.repo, Submodule.NULL_BIN_SHA, name='module', path=path, url='unused'
        )

    def test_update_rejects_outside_checkout_paths_before_clone(self) -> None:
        outside = self.root / 'outside'
        for path in ('../outside', 'nested/../../outside', str(outside)):
            with self.subTest(path=path), patch.object(
                Submodule, '_clone_repo', side_effect=AssertionError('clone attempted')
            ) as clone:
                with self.assertRaisesRegex(ValueError, 'is not in repository'):
                    self.submodule(path).update(init=True)
                clone.assert_not_called()
                self.assertFalse(outside.exists())

    def test_update_rejects_symlink_checkout_without_touching_target(self) -> None:
        target = self.root / 'target'
        target.mkdir()
        sentinel = target / 'sentinel'
        sentinel.write_text('unchanged', encoding='utf-8')
        (self.root / 'parent' / 'link').symlink_to(target, target_is_directory=True)
        with patch.object(
            Submodule, '_clone_repo', side_effect=AssertionError('clone attempted')
        ) as clone:
            with self.assertRaisesRegex(ValueError, 'contains a symbolic link'):
                self.submodule('link/module').update(init=True)
            clone.assert_not_called()
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'unchanged')
        self.assertEqual(list(target.iterdir()), [sentinel])

    def test_update_rejects_repository_root_as_checkout(self) -> None:
        with patch.object(
            Submodule, '_clone_repo', side_effect=AssertionError('clone attempted')
        ) as clone:
            with self.assertRaisesRegex(ValueError, 'must not be the repository root'):
                self.submodule('.').update(init=True)
            clone.assert_not_called()

    def test_update_never_clones_through_collapsed_symlink(self) -> None:
        target = self.root / 'external'
        anchor = target / 'anchor'
        anchor.mkdir(parents=True)
        (self.root / 'parent' / 'link').symlink_to(anchor, target_is_directory=True)

        class CloneIntercepted(RuntimeError):
            pass

        with patch.object(Repo, 'clone_from', side_effect=CloneIntercepted) as clone:
            try:
                self.submodule('link/../escaped').update(init=True)
            except ValueError:
                clone.assert_not_called()
            except CloneIntercepted:
                # Canonicalizing a safe destination is also acceptable, provided
                # the actual clone sink never receives the unsafe raw path.
                destination = Path(clone.call_args.args[1]).resolve()
                self.assertTrue(destination.is_relative_to(self.root / 'parent'))
            else:
                self.fail('Update neither rejected the path nor reached the guarded clone')
        self.assertEqual(list(target.iterdir()), [anchor])

    def test_valid_nested_checkout_remains_supported(self) -> None:
        module = self.submodule('libs/module')
        with patch.object(
            Submodule, '_clone_repo', side_effect=AssertionError('clone attempted')
        ) as clone:
            self.assertIs(module.update(init=True, dry_run=True), module)
            clone.assert_not_called()
        self.assertEqual(Path(module.abspath), self.root / 'parent' / 'libs' / 'module')
        self.assertFalse((self.root / 'parent' / 'libs').exists())

    def test_streamlit_can_still_read_local_repository_metadata(self) -> None:
        script = self.root / 'parent' / 'app.py'
        script.write_text('# local fixture\n', encoding='utf-8')
        repo = GitRepo(str(script))
        self.assertIsNotNone(repo.repo)
        self.addCleanup(repo.repo.close)
        self.assertTrue(repo.is_valid())
        self.assertEqual(repo.module, 'app.py')
        self.assertIn('app.py', repo.untracked_files)
