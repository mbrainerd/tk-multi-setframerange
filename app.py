# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
An app that syncs the frame range between a scene and a shot in Shotgun.

"""

import sys
import os

from tank.platform import Application
from tank.platform.qt import QtCore, QtGui
import tank


class SetFrameRange(Application):

    # declared here it is accesible to hooks without funky imports
    class FrameOperationNotSupported(Exception):
        pass

    class NoDefaultRangeDefined(Exception):
        pass

    def init_app(self):
        """
        App entry point
        """
        # make sure that the context has an entity associated - otherwise it wont work!
        if self.context.entity is None:
            raise tank.TankError("Cannot load the Set Frame Range application! "
                                 "Your current context does not have an entity (e.g. "
                                 "a current Shot, current Asset etc). This app requires "
                                 "an entity as part of the context in order to work.")

        self.engine.register_command("Sync Frame Range with Shotgun", self.run_app)

    @property
    def context_change_allowed(self):
        """
        Specifies that context changes are allowed.
        """
        return True

    def destroy_app(self):
        """
        App teardown
        """
        self.log_debug("Destroying sg_set_frame_range")


    def run_app(self):
        """
        Callback from when the menu is clicked.
        """

        message = ""
        try:
            try:
                new_in, new_out = self.get_frame_range_from_shotgun()
                if new_in is None or new_out is None:
                    message = "Shotgun has not yet been populated with \n"
                    message += "in and out frame data for this Shot."
                    QtGui.QMessageBox.information(None, "No data in Shotgun!", message)
                    return
                msg = "latest frame range from shotgun"
            except self.FrameOperationNotSupported as e:
                if not self.get_setting("use_default_values"):
                    raise e
                else:
                    message += "{0} and ".format(str(e))
                    new_in, new_out = self.get_default_frame_range()
                    msg = "default frame range"
        except (self.FrameOperationNotSupported, self.NoDefaultRangeDefined) as e:
            message += "{0} {1}".format(str(e), "\nNot Updating frame range.")
            QtGui.QMessageBox.information(None, str(e.__class__.__name__), message)
        else:
            current_in, current_out = self.get_current_frame_range()
            # now update the frame range.
            # because the frame range is often set in multiple places (e.g render range,
            # current range, anim range etc), we go ahead an update every time, even if
            # the values in Shotgun are the same as the values reported via get_current_frame_range()
            updated = self.set_frame_range(new_in, new_out)

            if updated:
                message =  "Your scene has been updated with the \n"
                message += "{}.\n\n".format(msg)
                message += "Previous start frame: %s\n" % current_in
                message += "New start frame: %s\n\n" % new_in
                message += "Previous end frame: %s\n" % current_out
                message += "New end frame: %s\n\n" % new_out

                QtGui.QMessageBox.information(None, "Frame range updated!", message)
            else:
                message =  "There was a problem updating your scene frame range.\n"
                QtGui.QMessageBox.warning(None, "Frame range not updated!", message)




    ###############################################################################################
    # implementation


    def get_frame_range_from_shotgun(self):
        """
        Returns (in, out) frames from shotgun.
        """
        # we know that this exists now (checked in init)
        entity = self.context.entity

        sg_entity_type = self.context.entity["type"]
        sg_filters = [["id", "is", entity["id"]]]

        sg_in_field = self.get_setting("sg_in_frame_field")
        sg_out_field = self.get_setting("sg_out_frame_field")
        fields = [sg_in_field, sg_out_field]

        data = self.shotgun.find_one(sg_entity_type, filters=sg_filters, fields=fields)

        if sg_in_field not in data:
            raise self.FrameOperationNotSupported("Configuration error: Your current context is connected to a Shotgun "
                                                  "%s. This entity type does not have a field %s.%s"
                                                  % (sg_entity_type, sg_entity_type, sg_in_field))

        if sg_out_field not in data:
            raise self.FrameOperationNotSupported("Configuration error: Your current context is connected to a Shotgun "
                                                  "%s. This entity type does not have a field %s.%s"
                                                  % (sg_entity_type, sg_entity_type, sg_out_field))

        return data[sg_in_field], data[sg_out_field]

    def get_current_frame_range(self):
        try:
            result = self.execute_hook("hook_frame_operation",
                                       operation="get_frame_range")
        except self.FrameOperationNotSupported as e:
            self.log_debug(str(e))
        except:
            raise

        if not isinstance(result, tuple) or (isinstance(result, tuple) and len(result) != 2):
            raise TypeError("Unexpected type returned from 'hook_frame_operation' for operation get_frame_range."
                            "Expected a 'tuple' with (in_frame, out_frame) values but returned '%s' : %s"
                            % type(result).__name__, result)
        return result 

    def set_frame_range(self, in_frame, out_frame):
        try:
            result = self.execute_hook("hook_frame_operation",
                                       operation="set_frame_range",
                                       in_frame=in_frame,
                                       out_frame=out_frame)
        except self.FrameOperationNotSupported as e:
            self.log_debug(str(e))
        except:
            raise

        return result

    def get_default_frame_range(self):
        try:
            default_values = self.get_setting("default_sg_frame_values")
            default_in = default_values['default_sg_in_frame_value']
            default_out = default_values["default_sg_out_frame_value"]
        except KeyError as e:
            raise self.NoDefaultRangeDefined("{}".format(e))
        return default_in, default_out
