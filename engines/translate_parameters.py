from engines.validate_parameters import read_parameter_from_schema
from engines.common import read_json
from engines.process_tesseract import *
from engines import data_folder, tmp_folder, act_environ, deact_environ
from engines.common import split_train_test
import numpy as np
from engines.translate_model import ModelTranslator


def read_parameter_default(engine):
    common_schema = read_json("engines/schemas/common.schema")
    default_values = {}
    for key in common_schema["definitions"]:
        default_values[key] = common_schema["definitions"][key]["default"]
    engine_schema = read_json("engines/schemas/engine_%s.schema" % engine)
    for key in engine_schema["properties"]:
        if key not in default_values and key != "model" and key != "engine":
            if engine_schema["properties"][key]["type"] == "object":
                for ele in engine_schema["properties"][key]["properties"]:
                    new_key = '%s_%s' % (key, ele)
                    default_values[new_key] = engine_schema["properties"][key]["properties"][ele]["default"]
            else:
                default_values[key] = engine_schema["properties"][key]["default"]
    return default_values


def read_value(configs, engine):
    default_values = read_parameter_default(engine)
    values = {}
    for k in configs:
        if type(configs[k]) is dict:
            for ele in configs[k]:
                new_key = '%s_%s' % (k, ele)
                values[new_key] = configs[k][ele]
        else:
            values[k] = configs[k]
    for ele in default_values:
        if ele not in values:
            values[ele] = default_values[ele]
    return values

    # self.values = {k: self.configs[k] if k in self.configs else self.default[k] for k in
    #                self.default}  # Rewrite value according to user specific configuration


def files2str(setname, catstr):
    a = []
    with open(pjoin(tmp_folder, 'list.%s' % setname)) as f_:
        for line in f_:
            a.append(line.strip())
            # a.append(os.path.join(os.getcwd(), line.strip()))
    res_str = catstr.join(a)
    return res_str


class Translate:
    def __init__(self, file_config, model_dir):
        self.configs = read_json(pjoin('static/configs', file_config))
        self.engine = self.configs["engine"]
        self.model_dir = model_dir

        self.translator = read_json('engines/schemas/translate.json')[self.engine]

        # load default values
        # self.default = read_parameter_default(self.engine)
        # replace default values with user specified values
        self.values = read_value(self.configs, self.engine)
        self.model_translator = ModelTranslator(self.configs["model"], self.engine)

        self.model_prefix = self.values["model_prefix"]
        self.nepoch = self.values['nepoch']
        partition = self.values['partition']
        self.ntrain, self.ntest = split_train_test(data_folder,
                                                   tmp_folder,
                                                   partition,
                                                   engine=self.engine)

        self.translate()
        self.cmd_list = [act_environ(self.engine)] + self.cmd_list + [deact_environ]\
            if self.engine != 'tesseract' else self.cmd_list

    def translate(self):
        method = getattr(self, self.engine, lambda: "Invalid Engine")
        return method()

    # def values(self, key):
    #     return self.configs[key] if key in self.configs else self.default[key]

    def tesseract(self):
        model_folder = self.model_dir
        checkpoint_folder = pjoin(self.model_dir, 'checkpoint')
        preprocess(data_folder, tmp_folder, model_folder, checkpoint_folder, self.model_prefix)
        # partition
        cmd = 'lstmtraining --traineddata %s --train_listfile %s ' %\
              (pjoin(model_folder, self.model_prefix, self.model_prefix + '.traineddata'),
               pjoin(tmp_folder, 'list.train'))
        if self.ntest > 0:
            cmd += '--eval_listfile %s ' % pjoin(tmp_folder, 'list.eval')

        # nepoch
        max_iter = int(self.nepoch * np.ceil(self.ntrain / self.values["batch_size"]))
        cmd += '--%s %d ' % (self.translator["nepoch"], max_iter)

        # model_prefix
        cmd += '--%s %s ' % (self.translator['model_prefix'],
                           pjoin(checkpoint_folder, self.model_prefix))

        # append
        flag_append = False if self.values["append"] == -1 and len(self.values["continue_from"]) == 0 else True

        # model
        # voc_size = get_numofchar(tmp_folder)
        cmd += '%s ' % self.model_translator.tesseract(self.values["batch_size"], flag_append)

        floats = ["append",  "continue_from",
                  "optimizer", "momentum", "adam_beta",
                  "target_error_rate",
                  "perfect_sample_delay"]
        for para in self.configs:
            if para not in floats:
                continue
            else:
                para_name = self.translator[para] if para in self.translator else para
                cmd += '--%s %s ' % (para_name, str(self.values[para]))
        print(cmd)
        self.cmd_list = [cmd]

    def kraken(self):
        print(self.configs)
        # Partition
        cmd = 'ketos train -t %s -e %s ' % (pjoin(tmp_folder, 'list.train'),
                                                 pjoin(tmp_folder, 'list.eval'))
        # model_prefix
        cmd += '--%s %s ' % (self.translator['model_prefix'],
                           pjoin(self.model_dir, self.model_prefix))
        # nepoch
        cmd += '--%s %d ' % (self.translator['nepoch'], self.nepoch)
        # save_freq
        cmd += '--savefreq %.1f ' % self.values['savefreq']
        # learning_rate
        cmd += '--%s %f ' % (self.translator['learning_rate'], self.values['learning_rate'])
        # append
        flag_append = False if self.values["append"] == -1 and len(self.values["continue_from"]) == 0 else True

        # model
        cmd += '%s ' % self.model_translator.kraken(self.values["batch_size"], flag_append)  # model specification

        # early stop
        if 'early_stop' in self.configs:
            cmd += '--%s early ' % self.translator['early_stop']
            if 'min_improve' in self.configs["early_stop"]:
                cmd += '--%s %f ' % (self.translator['early_stop_min_improve'],
                                   self.values['early_stop_min_improve'])
            if 'nbest' in self.configs["early_stop"]:
                cmd += '--%s %d ' % (self.translator['early_stop_nbest'],
                                   self.values['early_stop_nbest'])
        else:
            cmd += '--%s dumb ' % self.translator['early_stop']

        floats = ["append", "continue_from",
                  "optimizer", "momentum", "schedule", "weight_decay",
                  "preload", "device", "threads",
                  "normalization", "normalize-whitespace",
                  "codec", "resize", "reorder"]

        for para in self.configs:
            if para not in floats:
                continue
            para_name = self.translator[para] if para in self.translator else para
            if para in ['preload', 'reorder', "normalize-whitespace"]:
                if self.values[para]:
                    cmd += '--%s ' % para_name
                else:
                    cmd += '--no-%s' % para_name
            else:
                cmd += '--%s %s ' % (para_name, self.values[para])
        print(cmd)
        self.cmd_list = [cmd]

    def ocropus(self):
        # partition
        train_str = files2str('train', ' ')
        if self.ntest > 0:
            test_str = files2str('eval', ':')
            cmd = 'ocropus-rtrain %s -t %s ' % (train_str, test_str)
        else:
            cmd = 'ocropus-rtrain %s/*.png ' % data_folder

        # nepoch
        max_iter = self.nepoch * self.ntrain
        cmd += '--%s %d ' % (self.translator["nepoch"], max_iter)

        # model_prefix
        cmd += '--%s %s ' % (self.translator['model_prefix'],
                           pjoin(self.model_dir, self.model_prefix))
        # save_freq
        save_freq = int(self.values['savefreq'] * self.ntrain)
        cmd += '--savefreq %d ' % save_freq

        # model
        cmd += '%s ' % self.model_translator.ocropus()

        # learning_rate
        cmd += '--%s %f ' % (self.translator['learning_rate'], self.values['learning_rate'])

        floats = ["start", "codec"]
        for para in self.configs:
            if para not in floats:
                continue
            para_name = self.translator[para] if para in self.translator else para
            if para == 'codec':
                cmd += '--%s %s' % (para_name, ' '.join(['\'' + ele + '\'' for ele in self.values[para]]))
            else:
                cmd += '--%s %s ' % (para_name, self.values[para])
        # print(cmd)
        self.cmd_list = [cmd.strip()]

    def calamari(self):
        # partition
        train_str = files2str('train', ' ')
        if self.ntest > 0:
            test_str = files2str('eval', ' ')
            cmd = 'calamari-train --files %s --validation %s ' % (train_str, test_str)
        else:
            cmd = 'calamari-train --files %s/*.png ' % data_folder

        # nepoch
        batch_size = self.values["batch_size"]
        max_iter = self.nepoch * int(np.ceil(self.ntrain / batch_size))
        cmd += '--%s %d ' % (self.translator['nepoch'], max_iter)

        # savefreq
        cmd += '--%s %.1f ' % (self.translator['savefreq'], self.values['savefreq'])

        # model_prefix
        if self.model_prefix[-1] != '_':
            self.model_prefix += '_'
        cmd += '--%s %s ' % (self.translator['model_prefix'], self.model_prefix)
        cmd += '--output_dir %s ' % self.model_dir

        # model
        cmd += self.model_translator.calamari(learning_rate=self.values["learning_rate"]) + ' '

        floats = ["batch_size",
                  "continue_from",
                  "no_skip_invalid_gt",
                  "gradient_clipping_mode",
                  "gradient_clipping_const",
                  "backend"]
        floats_hier = ["early_stop", "num_threads", "preload"]
        for para in self.configs:
            if para not in floats and para not in floats_hier:
                continue
            if para in floats:
                if para == 'no_skip_invalid_gt':
                    if self.configs[para]:
                        cmd += '--no_skip_invalid_gt '
                else:
                    para_name = self.translator[para] if para in self.translator else para
                    cmd += '--%s %s ' % (para_name, str(self.values[para]))
            elif para in floats_hier:
                for ele in self.configs[para]:
                    fullname = '%s_%s' % (para, ele)
                    para_name = self.translator[fullname] if fullname in self.translator else fullname
                    if "preload" in fullname:
                        if self.values[fullname]:
                            cmd += '--%s ' % para_name
                    else:
                        cmd += '--%s %s ' % (para_name, str(self.values[fullname]))
        print(cmd)
        self.cmd_list = [cmd]


def test():
    translate = Translate('sample_kraken.json', model_dir='static/model/kraken')
    print(translate.cmd_list)


test()
