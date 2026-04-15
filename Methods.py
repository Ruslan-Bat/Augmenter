import os
from typing import List, Tuple

import cv2
import inspect
try:
    from Project.augmentations_library.Loader import ImageLoader, NoiseLoader
except Exception:
    try:
        from Project.augmentations_library.Loader import ImageLoader, NoiseLoader
    except Exception:
        # last resort: add Project folder to path
        import sys
        import os as _os
        sys.path.insert(0, _os.path.join(os.path.dirname(__file__), 'Project'))
        try:
            from Project.augmentations_library.Loader import ImageLoader, NoiseLoader
        except Exception:
            raise


class AugmentationManager:
    """Утилитарный класс для получения списка эффектов и пакетной аугментации.

    Использует `augmentations_library.Loader.NoiseLoader` и `ImageLoader`.
    """

    def __init__(self, library_name: str = 'augmentations_library.Effects'):
        self.library_name = library_name
        self.noise_loader = NoiseLoader(library_name=self.library_name)

    def list_effects_for_ui(self) -> List[Tuple[str, str, str]]:
        """Возвращает список кортежей (id, label, description) для UI.

        id: строковое имя класса (используется как идентификатор)
        label: читаемое имя (если есть attribute `display_name`, берётся он, иначе имя класса)
        description: первая строка docstring класса или пустая строка
        """
        results = []
        # start listing effects
        # try several candidate module names to account for running from project root
        candidates = [self.library_name,
                      f"Project.{self.library_name}",
                      'augmentations_library',
                      'Project.augmentations_library',
                      'Project.augmentations_library.Effects']
        names = None
        for cand in candidates:
            try:
                self.noise_loader.library_name = cand
                names = self.noise_loader.list_available()
                # keep candidate that worked
                self.library_name = cand
                break
            except Exception:
                names = None
                continue
        if names is None:
            return []

        # динамически импортим класс объекты
        for cls_name in names:
            try:
                cls = self.noise_loader.load_class(cls_name)
                label = getattr(cls, 'display_name', cls.__name__)
                doc = (cls.__doc__ or '').strip().splitlines()
                descr = doc[0] if doc else ''
                results.append((cls_name, label, descr))
            except Exception:
                continue
        return results

    def batch_augment(self, src_dir: str, dst_dir: str, methods: List[str]) -> str:
        """Пакетно обрабатывает изображения из `src_dir` и сохраняет в `dst_dir`.

        `methods` - список имён классов эффектов (как возвращает `list_effects_for_ui`).
        Возвращает русскоязычную строку с результатом.
        """
        if not os.path.isdir(src_dir):
            return "Ошибка, попробуйте еще раз"
        os.makedirs(dst_dir, exist_ok=True)

        img_loader = ImageLoader()
        errors = False
        saved_count = 0

        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        files = []
        for root, _, filenames in os.walk(src_dir):
            for f in filenames:
                if os.path.splitext(f)[1].lower() in exts:
                    files.append(os.path.join(root, f))

        if not files:
            return "Ошибка, попробуйте еще раз", 0

        # load all original images first (use ImageLoader) to be able to supply secondary images
        originals = []
        for fpath in files:
            loader_tmp = ImageLoader()
            img0 = loader_tmp.load(fpath)
            if img0 is None:
                return "Ошибка, попробуйте еще раз", 0
            originals.append((fpath, img0))

        # create staging directory for atomic behavior: don't write to dst until all succeed
        import tempfile
        staging_root = tempfile.mkdtemp(prefix='augment_staging_')

        # process files and write outputs to staging
        for idx, (fpath, orig_img) in enumerate(originals):
            try:
                # work on a copy of the original to preserve source
                img = orig_img.copy()

                applied_names = []
                # применяем эффекты последовательно; abort on any failure
                for m in methods:
                    try:
                        klass = self.noise_loader.load_class(m)
                    except Exception:
                        errors = True
                        break

                    # prepare kwargs based on constructor signature
                    ctor_sig = inspect.signature(klass.__init__)
                    ctor_params = list(ctor_sig.parameters.keys())
                    kwargs = {}
                    if 'secondary_image' in ctor_params:
                        # choose next image as secondary if available, otherwise black image
                        if len(originals) > 1:
                            sec_img = originals[(idx + 1) % len(originals)][1]
                        else:
                            sec_img = (orig_img * 0).astype(orig_img.dtype)
                        kwargs['secondary_image'] = sec_img

                    try:
                        effect = klass(**kwargs) if kwargs else klass()
                    except Exception:
                        errors = True
                        break

                    try:
                        img = effect.apply(img)
                        applied_names.append(m)
                    except Exception:
                        errors = True
                        break

                if errors:
                    # abort processing
                    break

                # ensure at least one effect applied; otherwise consider as failure
                if not applied_names:
                    errors = True
                    break

                # сохраняем итоговое изображение в staging
                rel_dir = os.path.relpath(os.path.dirname(fpath), src_dir)
                staging_dir = os.path.join(staging_root, rel_dir) if rel_dir != '.' else staging_root
                os.makedirs(staging_dir, exist_ok=True)

                base = os.path.splitext(os.path.basename(fpath))[0]
                ext = os.path.splitext(fpath)[1]
                # save with same base name to keep count == input count
                target = os.path.join(staging_dir, f"{base}{ext}")
                try:
                    img_loader.save(target, img)
                    saved_count += 1
                except Exception:
                    errors = True
                    break
            except Exception:
                errors = True
                break

        # if any errors, cleanup staging and return error with 0 saved
        import shutil
        if errors:
            try:
                shutil.rmtree(staging_root)
            except Exception:
                pass
            return "Ошибка, попробуйте еще раз", 0

        # all succeeded -> move staging contents into dst
        for root, _, filenames in os.walk(staging_root):
            rel = os.path.relpath(root, staging_root)
            target_root = os.path.join(dst_dir, rel) if rel != '.' else dst_dir
            os.makedirs(target_root, exist_ok=True)
            for f in filenames:
                s = os.path.join(root, f)
                t = os.path.join(target_root, f)
                # if target exists, overwrite
                try:
                    shutil.move(s, t)
                except Exception:
                    try:
                        shutil.copy2(s, t)
                    except Exception:
                        pass

        # remove staging
        try:
            shutil.rmtree(staging_root)
        except Exception:
            pass

        status = "Аугментация прошла успешно"
        return status, saved_count
